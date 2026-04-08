class ChatSerializer:
    """Serializer cho Chat Request"""
    
    def __init__(self, data):
        self.data = data
        self.errors = {}
        self.validated_data = {}
    
    def is_valid(self):
        """Kiểm tra dữ liệu có hợp lệ không"""
        if not isinstance(self.data, dict):
            self.errors['message'] = 'Data phải là một dictionary'
            return False
        
        message = self.data.get('message', '').strip()
        
        if not message:
            self.errors['message'] = 'Trường message không được để trống'
            return False
        
        if len(message) > 1000:
            self.errors['message'] = 'Trường message không vượt quá 1000 ký tự'
            return False
        
        self.validated_data['message'] = message
        return True

