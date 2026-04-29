import pdfplumber
import re
import os
import unicodedata
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


    def clean_text(self, text: str) -> str:

        text = unicodedata.normalize("NFC", text)

        # ==========================================
        # BƯỚC 2: Xóa ký tự nhiễu & separator
        # ==========================================
        text = re.sub(r'[\*\-\_]{3,}', '', text)
        # Xóa ký tự không in được (giữ lại newline)
        text = re.sub(r'[^\S\n]+', ' ', text)  # normalize space, giữ \n

        # ==========================================
        # BƯỚC 3: Xóa boilerplate pháp lý
        # ==========================================

        # Quốc hiệu / Tiêu ngữ — có thể xuất hiện theo nhiều thứ tự
        text = re.sub(
            r'(QUỐC HỘI|CHÍNH PHỦ|BỘ\s+\S+)\s+'
            r'CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM',
            '', text
        )
        text = re.sub(r'Độc\s+lập\s*[-–]\s*Tự\s+do\s*[-–]\s*Hạnh\s+phúc', '', text)
        text = re.sub(r'CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM', '', text)

        # Số hiệu văn bản — mở rộng pattern
        text = re.sub(r'Số\s*:\s*[\d/A-Z-]+', '', text, flags=re.IGNORECASE)

        # Địa danh + ngày tháng ký
        text = re.sub(
            r'[\w\s\.,]{2,30},\s*ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}',
            '', text
        )

        # Header luật
        text = re.sub(
            r'LUẬT\s+(CỦA\s+)?QUỐC\s+HỘI\s+NƯỚC\s+CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM',
            '', text
        )

        # Chữ ký, chức danh cuối văn bản
        text = re.sub(r'Nơi\s+nhận\s*:.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(
            r'(TM | KT\.\s*)?(THỦ TƯỚNG|PHÓ THỦ TƯỚNG|CHỦ TỊCH QUỐC HỘI|BỘ TRƯỞNG|CHÁNH VĂN PHÒNG).*?(ĐÃ KÝ|đã ký)?',
            '', text, flags=re.DOTALL
        )

        # ==========================================
        # BƯỚC 4: Xóa phần "Căn cứ" (an toàn hơn)
        # ==========================================
        # Dùng lookahead chặt hơn, tránh ăn vào nội dung chính
        text = re.sub(
            r'(Căn\s+cứ\s+(vào\s+)?|Để\s+tăng\s+cường\s+)(.*?)'
            r'(?=\n\s*(Chương|Điều)\s+[IVXLC\d]+)',
            '',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )

        # ==========================================
        # BƯỚC 5: Normalize cấu trúc điều khoản
        # (TRƯỚC khi nối dòng — thứ tự quan trọng!)
        # ==========================================

        # Đảm bảo Chương/Điều luôn bắt đầu dòng mới
        text = re.sub(r'[ \t]*(Chương\s+[IVXLC\d]+)', r'\n\1', text)
        text = re.sub(r'[ \t]*(Điều\s+\d+[\.\:]?)', r'\n\1', text)

        # Khoản dạng "1." hoặc "Khoản 1" — thêm dòng mới
        text = re.sub(r'[ \t]*(?<!\d)(\d{1,2}\.\s+[A-ZĐÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂẮẶẴẮĐ])', r'\n\1', text)
        text = re.sub(r'[ \t]*(Khoản\s+\d+)', r'\n\1', text)

        # Điểm a), b), c)...
        text = re.sub(r'[ \t]*([a-zđ]\)\s)', r'\n\1', text)

        # ==========================================
        # BƯỚC 6: Nối dòng bị wrap (chỉ dòng thường)
        # ==========================================
        # Nối dòng NẾU dòng trước không kết thúc bằng .;: 
        # VÀ dòng sau không bắt đầu bằng cấu trúc pháp lý
        text = re.sub(
            r'(?<![\.;:\n])\n(?!\s*(Chương|Điều|Khoản|\d{1,2}\.|[a-zđ]\)))',
            ' ',
            text
        )

        # ==========================================
        # BƯỚC 7: Fix lỗi OCR phổ biến
        # ==========================================
        # Số tiền bị tách (100 000 → 100000)
        text = re.sub(r'(\d{1,3})\s+(\d{3})(?=\s*(đồng|VNĐ|vnđ))', r'\1\2', text)
        # Chữ l bị nhận nhầm thành 1
        text = re.sub(r'\bl(\d{5,})\b', r'1\1', text)
        # "Điề u" bị tách
        text = re.sub(r'[,;]?\s*trừ các hành vi vi phạm quy định tại.*?(?=[.;\n]|$)', '', text, flags=re.IGNORECASE)
    
        # Xóa các cụm 'theo quy định tại Điều... khoản...' mang tính dẫn chiếu rác
        text = re.sub(r'quy định tại (điểm|khoản|Điều) \d+.*?(?=[,.;\n]|$)', '', text, flags=re.IGNORECASE)

        # ==========================================
        # BƯỚC 8: Dọn dẹp cuối
        # ==========================================
        text = re.sub(r'[ \t]+', ' ', text)          # nhiều space → 1
        text = re.sub(r'\n{3,}', '\n\n', text)        # nhiều newline → 2
        text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)  # xóa dòng trống
        text = re.sub(
        r'(Điều|Khoản|Chương)\s*\n\s*(\d+)',
        r'\1 \2',
        text    
        )
        text = re.sub(
        r'(Điều\s+\d+)\s*\n\s*([A-ZĐÀÁÂÃ])',
        r'\1. \2',
        text
        )


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