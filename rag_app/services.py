import os
import traceback
import time
from pgvector.django import L2Distance
from langchain_huggingface import HuggingFaceEmbeddings
from huggingface_hub import InferenceClient
from rag_app.models import TrafficLawChunk

# Cấu hình Hugging Face Inference API
hf_api_key = os.getenv('HUGGINGFACEHUB_API_KEY')
repo_id = "Qwen/Qwen2.5-7B-Instruct"

llm_client = InferenceClient(
    model=repo_id,
    token=hf_api_key,
)

# Embedding model
embedding_model = HuggingFaceEmbeddings(model_name="keepitreal/vietnamese-sbert")

def get_ai_response(question, history=None):
    """
    Trích lục câu trả lời từ Hugging Face API dựa trên RAG
    
    Args:
        input (str): Câu hỏi từ user
        history (list): Lịch sử chat (tuỳ chọn) - để AI hiểu ngữ cảnh
    
    Returns:
        dict: {'answer': str, 'sources': [str]}
    """
    max_retries = 2
    
    try:
        # Tạo embedding cho câu hỏi
        question_embedding = embedding_model.embed_query(question)
        
        # Tìm 5 chunks có similarity cao nhất
        relevant_chunks = list(TrafficLawChunk.objects.annotate(
            distance=L2Distance('embedding', question_embedding)
        ).order_by('distance')[:5])

        if not relevant_chunks:
            return {
                'answer': 'Xin lỗi, tôi không tìm được thông tin liên quan trong cơ sở dữ liệu luật của mình.',
                'sources': []
            }

        context = '\n'.join([chunk.content for chunk in relevant_chunks])
        
        # Build history context
        history_context = ""
        if history and len(history) > 0:
            history_context = "\nNGỮ CẢNH CÁC CÂU HỎI TRƯỚC:\n"
            for item in history[-3:]:
                history_context += f"- User: {item.get('question', '')}\n"
                history_context += f"- AI: {item.get('answer', '')[:200]}...\n"
        
        prompt = f"""Bạn là một Chuyên gia Tư vấn Luật Giao thông đường bộ Việt Nam cực kỳ tận tâm và chính xác.
Dưới đây là thông tin được trích xuất từ cơ sở dữ liệu pháp luật (Nghị định xử phạt, Luật Giao thông):

<TÀI LIỆU_THAM_KHẢO>
{context}
<TÀI LIỆU_THAM_KHẢO>

<NHIỆM_VỤ>
Dựa TRỰC TIẾP và DUY NHẤT vào <TÀI LIỆU_THAM_KHẢO> ở trên, hãy trả lời câu hỏi của người dùng: "{question}"
</NHIỆM_VỤ>

<QUY_TẮC_TRẢ_LỜI_BẮT_BUỘC>
1. TÍNH CHI TIẾT: TUYỆT ĐỐI KHÔNG tóm tắt chung chung các hành vi vi phạm. Nếu tài liệu liệt kê các điểm a, b, c, d..., bạn phải liệt kê chi tiết từng hành vi đó ra bằng gạch đầu dòng.
2. MỨC PHẠT & HÌNH PHẠT BỔ SUNG: Nếu câu hỏi liên quan đến vi phạm hành chính, phải nêu rõ số tiền phạt (in đậm) và các hình phạt bổ sung (như tước bằng lái, tịch thu xe) nếu có trong tài liệu.
3. TRÍCH DẪN RÕ RÀNG: Không cắt bỏ các trường hợp ngoại lệ. (Ví dụ: phải giữ nguyên các cụm từ "trừ các hành vi vi phạm tại điểm...").
4. XỬ LÝ KHI THIẾU THÔNG TIN: Nếu <TÀI LIỆU_THAM_KHẢO> hoàn toàn không chứa câu trả lời cho câu hỏi, hãy thành thật đáp: "Dựa trên dữ liệu hiện tại, tôi chưa tìm thấy quy định cụ thể về vấn đề này." Tuyệt đối không tự bịa ra luật hay lấy kiến thức bên ngoài.
5. VĂN PHONG: Chuyên nghiệp, rõ ràng, dễ hiểu. Sử dụng markdown để format câu trả lời (in đậm số tiền, dùng danh sách bullet point).
</QUY_TẮC_TRẢ_LỜI_BẮT_BUỘC>

{history_context}


CÂU TRẢ LỜI:"""
        
        response = None
        for attempt in range(max_retries):
            try:
                print(f"[HF] Gọi Hugging Face API (lần {attempt + 1}/{max_retries})...", flush=True)
                
                result = llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                    temperature=0.1,
                )
                response = result.choices[0].message.content
                
                if response and len(response.strip()) > 10:
                    print(f"[HF] ✓ Nhận response thành công", flush=True)
                    break
                    
            except Exception as retry_err:
                error_str = str(retry_err)
                print(f"[HF ERROR] Lỗi lần {attempt + 1}/{max_retries}: {error_str[:100]}", flush=True)
                
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    print(f"[HF] Chờ {wait_time}s trước khi thử lại...", flush=True)
                    time.sleep(wait_time)
                else:
                    raise
        
        if not response or len(response) < 10:
            return {
                'answer': 'Không thể lấy câu trả lời từ AI. Vui lòng thử lại.',
                'sources': []
            }
        
        # Trả về sources
        sources = list(set([chunk.source for chunk in relevant_chunks if chunk.source]))
            
        return {
            'answer': response.strip(),
            'sources': sources
        }
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] {error_msg}", flush=True)
        
        return {
            'answer': 'Hệ thống đang bận hoặc gặp sự cố. Vui lòng thử lại sau ít phút.',
            'sources': []
        }