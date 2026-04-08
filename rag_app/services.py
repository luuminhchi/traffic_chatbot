import os
import traceback
import time
import google.generativeai as genai
from django.conf import settings
from pgvector.django import L2Distance
from langchain_huggingface import HuggingFaceEmbeddings
from rag_app.models import TrafficLawChunk

# Cấu hình Gemini
google_api_key = os.getenv('GOOGLE_API_KEY')
model = 'models/gemini-2.5-flash'
if google_api_key:
    genai.configure(api_key=google_api_key)
    llm = genai.GenerativeModel(model)
else:
    raise ValueError("GOOGLE_API_KEY không được set trong environment variables")

# Embedding model
embedding_model = HuggingFaceEmbeddings(model_name="keepitreal/vietnamese-sbert")

def get_ai_response(input, history=None):
    """
    Trích lục câu trả lời từ Gemini API dựa trên RAG
    
    Args:
        input (str): Câu hỏi từ user
        history (list): Lịch sử chat (tuỳ chọn) - để AI hiểu ngữ cảnh
    
    Returns:
        dict: {'answer': str, 'sources': [str]}
    """
    max_retries = 2
    
    try:
        # Tạo embedding cho câu hỏi
        question_embedding = embedding_model.embed_query(input)
        
        # Tìm 5 chunks có similarity cao nhất (tăng từ 3 -> 5)
        relevant_chunks = TrafficLawChunk.objects.annotate(
            distance=L2Distance('embedding', question_embedding)
        ).order_by('distance')[:5]
        
        if not relevant_chunks.exists():
            return {
                'answer': 'Xin lỗi, tôi không tìm được thông tin liên quan trong cơ sở dữ liệu luật của mình.',
                'sources': []
            }
        
        context = '\n'.join([chunk.content for chunk in relevant_chunks])
        
        # Build history context (nếu có)
        history_context = ""
        if history and len(history) > 0:
            history_context = "\nNGỮ CẢNH CÁC CÂU HỎI TRƯỚC:\n"
            for item in history[-3:]:  # Lấy 3 câu gần nhất
                history_context += f"- User: {item['question']}\n"
                history_context += f"- AI: {item['answer'][:200]}...\n"
        
        # Prompt engineering nâng cao
        prompt = f"""Bạn là Trợ lý Luật Giao Thông Việt Nam thông minh, chuyên nghiệp và đáng tin cậy.

Nhiệm vụ của bạn:
1. Trích lục mức phạt/hình phạt CHÍNH XÁC từ văn bản được cung cấp
2. Nếu có nhiều mức phạt cho cùng hành vi, hãy liệt kê rõ theo loại phương tiện (xe máy, ô tô, v.v.)
3. Cung cấp những thông tin liên quan khác như mất giấy phép, tạm giữ xe, v.v.
4. Luôn kết thúc bằng câu: "Lưu ý: Thông tin chỉ mang tính chất tham khảo."

QUY TẮC:
- Nếu thông tin KHÔNG có trong tài liệu, hãy nói "Tôi không có thông tin..." ĐỪNG bịa
- Trả lời NGẮN GỌN nhưng ĐẦY ĐỦ (tối đa 500 ký tự)
- Dùng lời lẽ học thuật nhưng dễ hiểu

{history_context}

THÔNG TIN LUẬT:
{context}

CÂU HỎI CỦA USER:
{input}

CÂU TRẢ LỜI (phải theo đúng quy tắc trên):
"""
        
        # Gọi Gemini API với retry logic
        response = None
        for attempt in range(max_retries):
            try:
                response = llm.generate_content(prompt).text
                if response and response.strip():
                    break
            except Exception as retry_err:
                if attempt < max_retries - 1:
                    print(f"[RETRY] Lỗi, thử lại trong 2s... (lần {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    raise
        
        if not response or not response.strip():
            return {
                'answer': 'Không thể lấy câu trả lời từ AI. Vui lòng thử lại.',
                'sources': []
            }
        
        # Trả về sources (tên file, không lặp)
        sources = list(set([chunk.source for chunk in relevant_chunks]))
            
        return {
            'answer': response.strip(),
            'sources': sources
        }
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_msg}")
        return {
            'answer': 'Hệ thống đang bận hoặc gặp sự cố. Vui lòng thử lại sau ít phút.',
            'sources': []
        }