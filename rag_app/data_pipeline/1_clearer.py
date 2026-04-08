import pdfplumber
import re
import os
from pathlib import Path

class LegalDataCleaner:
    def __init__(self, input_folder, output_folder):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def extract_raw_text(self, pdf_path):
        """Trích xuất text thô từ PDF sử dụng pdfplumber"""
        full_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        return "\n".join(full_text)

    def clean_text(self, text):
        # 1. Xóa hàng dấu sao hoặc gạch ngang (********, --------)
        text = re.sub(r'[\*\-\_]{3,}', '', text)

        # 2. Xóa Quốc hiệu, Tiêu ngữ và tên cơ quan ban hành (QUỐC HỘI, CHÍNH PHỦ...)
        # Dùng (?i) để không phân biệt hoa thường nếu cần
        text = re.sub(r'(QUỐC HỘI|CHÍNH PHỦ)\s+CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', '', text)
        text = re.sub(r'Độc lập - Tự do - Hạnh phúc', '', text)

        # 3. Xóa Số hiệu văn bản (Ví dụ: Số: 26/2001/QH10)
        text = re.sub(r'Số:\s+\d+/\d+/[A-Z0-9-]+', '', text)

        # 4. Xóa địa danh, ngày tháng (Hà Nội, ngày... tháng... năm...)
        text = re.sub(r'[A-ZÀ-Ỹa-zà-ỹ\s\.]{2,},\s+ngày\s+\d+\s+tháng\s+\d+\s+năm\s+\d+', '', text)

        # 5. Xóa cụm từ lặp lại "LUẬT CỦA QUỐC HỘI NƯỚC..." 
        # (Giữ lại tên Luật "GIAO THÔNG ĐƯỜNG BỘ" ở dòng sau)
        text = re.sub(r'LUẬT CỦA QUỐC HỘI NƯỚC CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', '', text)

        # 6. XÓA PHẦN "CĂN CỨ" (Dành cho RAG: Phần này thường gây nhiễu vì toàn liệt kê các luật khác)
        # Tìm từ "Để tăng cường..." hoặc "Căn cứ vào..." cho đến khi gặp "Chương" hoặc "Điều"
        # Dùng flags=re.DOTALL để dấu chấm khớp với cả dòng mới
        text = re.sub(r'(Để tăng cường|Căn cứ vào).*?(?=(Chương|Điều)\s+\d+)', '', text, flags=re.DOTALL)

        # --- Các bước nối dòng và định dạng giữ nguyên ---
        text = re.sub(r'(?<![\.;:])\n', ' ', text)
        text = re.sub(r'\s+(Chương\s+\d+)', r'\n\1', text) # Thêm Chương vào danh sách xuống dòng
        text = re.sub(r'\s+(Điều\s+\d+)', r'\n\1', text)
        text = re.sub(r'\s+(Khoản\s+\d+)', r'\n\1', text)
        text = re.sub(r'\s+([a-zđ]\))', r'\n\1', text)

        # Dọn dẹp khoảng trắng thừa
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        
        return text.strip()
    
    def run_pipeline(self):
        """Chạy quy trình cho toàn bộ file trong thư mục"""
        pdf_files = list(self.input_folder.glob("*.pdf"))
        if not pdf_files:
            print("Không tìm thấy file PDF nào trong thư mục raw_data!")
            return

        for pdf_path in pdf_files:
            print(f"Đang xử lý: {pdf_path.name}...")
            
            # Trích xuất
            raw = self.extract_raw_text(pdf_path)
            
            # Làm sạch
            clean = self.clean_text(raw)
            
            # Lưu file
            output_file = self.output_folder / f"{pdf_path.stem}_cleaned.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(clean)
                
        print(f"Hoàn thành! Đã làm sạch {len(pdf_files)} file. Kiểm tra tại: {self.output_folder}")

# Chạy thử
if __name__ == "__main__":
    cleaner = LegalDataCleaner(
        input_folder="D:\\trafficChatbot\\rag_app\\data_pipeline\\raw_data",
        output_folder="D:\\trafficChatbot\\rag_app\\data_pipeline\\cleaned_data"
    )
    cleaner.run_pipeline()