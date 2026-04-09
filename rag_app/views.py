from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from rag_app.services import get_ai_response

# 1. Trang chủ: Hiển thị giao diện chat
def chat_home(request):
    return render(request, 'rag_app/chat.html')

# 2. API: Xử lý câu hỏi (với chat history)
@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    try:
        import sys
        data = json.loads(request.body)
        user_question = data.get('question', '').strip()
        chat_history = data.get('history', [])
        
        if not user_question:
            return JsonResponse({
                'success': False,
                'error': 'Vui lòng nhập câu hỏi'
            }, status=400)
        
        result = get_ai_response(user_question, history=chat_history)
        
        return JsonResponse({
            'success': True,
            'answer': result['answer'],
            'sources': result['sources']
        })
    
    except Exception as e:
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# 3. API: Lưu chat history vào session (FIFO Queue)
@csrf_exempt
@require_http_methods(["POST"])
def save_history(request):
    try:
        data = json.loads(request.body)
        new_conversation = data.get('history', [])
        conversation_index = data.get('conversation_index', -1)  # -1 = chat mới
        
        # Lấy danh sách conversations hiện tại
        conversations = request.session.get('chat_history', [])
        
        # Nếu conversations không phải là list, khởi tạo lại
        if not isinstance(conversations, list):
            conversations = []
        
        # Nếu index hợp lệ → UPDATE conversation đó (không append trùng)
        if isinstance(conversation_index, int) and 0 <= conversation_index < len(conversations):
            conversations[conversation_index] = new_conversation
        else:
            # Chat mới → Thêm vào cuối
            conversations.append(new_conversation)
            
            # Giữ tối đa 50 conversations (FIFO - xóa cái cũ nhất)
            if len(conversations) > 50:
                conversations.pop(0)
        
        request.session['chat_history'] = conversations
        request.session.modified = True
        
        return JsonResponse({'success': True, 'conversation_index': len(conversations) - 1})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# 4. API: Lấy chat history từ session
@require_http_methods(["GET"])
def get_history(request):
    try:
        history = request.session.get('chat_history', [])
        return JsonResponse({
            'success': True,
            'history': history
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# 5. API: Xóa chat history
@csrf_exempt
@require_http_methods(["POST"])
def clear_history(request):
    try:
        request.session['chat_history'] = []
        request.session.modified = True
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)