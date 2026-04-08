from django.contrib import admin
from django.urls import path, include
from rag_app import views as rag_views

# Danh sách các đường dẫn (URL) của dự án
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    # Chat routes - để cái này handle root path '/'
    path('', include('rag_app.urls')),
    # API endpoints
    path('api/', include([
        path('chat/', rag_views.chat_api, name='chat_api'),
        path('history/', rag_views.get_history, name='get_history'),
        path('history/save/', rag_views.save_history, name='save_history'),
        path('history/clear/', rag_views.clear_history, name='clear_history'),
    ])),
]