import os
import traceback
import time
from pgvector.django import CosineDistance
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


def get_ai_response(question, history=None):
    try:
        question_embedding = embedding_model.encode(question).tolist()

        relevant_chunks = list(
            TrafficLawChunk.objects.annotate(
                distance=CosineDistance('embedding', question_embedding)
            )
            .filter(distance__lt=0.5)
            .order_by('distance')[:5]
        )

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

        return {
            'answer': result.choices[0].message.content.strip(),
            'sources': list(set([c.source for c in relevant_chunks]))
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {'answer': 'Hệ thống đang bận. Vui lòng thử lại.', 'sources': []}
