import os
from pgvector.django import CosineDistance
from django.contrib.postgres.search import SearchQuery, SearchRank
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient
from rag_app.models import TrafficLawChunk
from rag_app.prompts import SYSTEM_PROMPT, build_user_prompt, build_history_context

# Cấu hình Hugging Face Inference API
hf_api_key = os.getenv('HUGGINGFACEHUB_API_KEY')
repo_id = "Qwen/Qwen2.5-7B-Instruct"

llm_client = InferenceClient(
    model=repo_id,
    token=hf_api_key,
)

# Embedding model (dùng SentenceTransformer để nhất quán với 3_embed.py)
embedding_model = SentenceTransformer("keepitreal/vietnamese-sbert")

# Số candidates lấy từ mỗi search trước khi fuse
_CANDIDATE_K = 20
# Tham số k trong công thức RRF: score = 1 / (k + rank)
_RRF_K = 60


def _hybrid_search(question_embedding, question_text, top_n=5):
    """
    Kết hợp Dense Vector Search + BM25 Full-text Search bằng Reciprocal Rank Fusion.
    Trả về danh sách TrafficLawChunk đã xếp hạng theo điểm RRF.
    """
    # --- Nhánh 1: Dense vector search (cosine similarity) ---
    vector_qs = list(
        TrafficLawChunk.objects.annotate(
            distance=CosineDistance('embedding', question_embedding)
        )
        .order_by('distance')[:_CANDIDATE_K]
    )

    # --- Nhánh 2: BM25 full-text search (PostgreSQL tsvector/tsquery) ---
    search_query = SearchQuery(question_text, config='simple')
    fts_qs = list(
        TrafficLawChunk.objects.annotate(
            rank=SearchRank('search_vector', search_query)
        )
        .filter(rank__gt=0)
        .order_by('-rank')[:_CANDIDATE_K]
    )

    # --- Reciprocal Rank Fusion ---
    rrf_scores: dict[int, float] = {}

    for i, chunk in enumerate(vector_qs):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (_RRF_K + i + 1)

    for i, chunk in enumerate(fts_qs):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (_RRF_K + i + 1)

    # Gom tất cả chunks vào dict, sắp xếp theo RRF score giảm dần
    all_chunks: dict[int, TrafficLawChunk] = {c.id: c for c in vector_qs + fts_qs}
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

    return [all_chunks[cid] for cid in sorted_ids[:top_n]]


def get_ai_response(question, history=None):
    try:
        question_embedding = embedding_model.encode(question).tolist()

        relevant_chunks = _hybrid_search(question_embedding, question, top_n=5)

        if not relevant_chunks:
            return {
                'answer': 'Dữ liệu hiện tại chưa có quy định về vấn đề này.',
                'sources': []
            }

        # Build context có header Điều
        context = '\n\n'.join([
            f"[Điều {c.dieu_num} - {c.source}]\n{c.content}"
            for c in relevant_chunks
        ])

        history_context = build_history_context(history)
        user_prompt = build_user_prompt(question, context, history_context)

        result = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            max_tokens=512,
            temperature=0.1,
        )
        answer = result.choices[0].message.content.strip()
        return {
            'answer': answer,
            'sources': list(set([c.source for c in relevant_chunks]))
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {'answer': 'Hệ thống đang bận. Vui lòng thử lại.', 'sources': []}
