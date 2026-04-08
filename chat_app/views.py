import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from chat_app.serializers import ChatSerializer
from rag_app.services import get_ai_response


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """
    API endpoint để xử lý chat requests
    
    POST /chat/api/
    
    Body:
    {
        "message": "Câu hỏi của bạn"
    }
    
    Response:
    {
        "answer": "Câu trả lời từ AI",
        "source": ["file1.pdf", "file2.pdf"]
    }
    """
    try:
        data = json.loads(request.body)
        serializer = ChatSerializer(data)
        
        if not serializer.is_valid():
            return JsonResponse(
                {"error": serializer.errors},
                status=400
            )
        
        message = serializer.validated_data['message']
        
        # Gọi RAG service để lấy câu trả lời
        response = get_ai_response(message)
        
        return JsonResponse(response, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON format"},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"Lỗi khi xử lý: {str(e)}"},
            status=500
        )


