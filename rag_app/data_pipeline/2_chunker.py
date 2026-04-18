import os
import re
from pathlib import Path
import json

class LegalChunker:
    def __init__(self, input_folder, output_file):
        self.input_folder = Path(input_folder)
        self.output_file = output_file

    def _clean_for_embedding(self, text):
        """Xóa nhiễu dẫn chiếu 'trừ các hành vi...' để tăng độ chính xác của Vector"""
        # 1. Xóa phần 'trừ các hành vi vi phạm quy định tại...' cho đến hết câu hoặc dấu chấm phẩy
        text = re.sub(r'[,;]?\s*trừ các hành vi vi phạm quy định tại.*?(?=[.;\n]|$)', '', text, flags=re.IGNORECASE)
        # 2. Xóa các cụm dẫn chiếu rác như 'theo quy định tại khoản...'
        text = re.sub(r'quy định tại (điểm|khoản|Điều) \d+.*?(?=[,.;\n]|$)', '', text, flags=re.IGNORECASE)
        return text.strip()

    def process_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = []
        # Tách thành từng Điều
        dieu_blocks = re.split(r'(?=\nĐiều\s+\d+)', content)

        for block in dieu_blocks:
            block = block.strip()
            if not block: continue

            # Extract thông tin Điều
            dieu_match = re.match(r'(Điều\s+(\d+)[\.\:]?\s*(.*))', block)
            if not dieu_match: continue

            dieu_header = dieu_match.group(1).split('\n')[0].strip()
            dieu_num = int(dieu_match.group(2))
            dieu_title = dieu_match.group(3).split('\n')[0].strip()

            # BƯỚC 2: Tách thành từng KHOẢN (1., 2., ...)
            khoan_blocks = re.split(r'(?=\n(?:Khoản\s+\d+|\d{1,2}\.\s+[A-ZĐÀÁÂ]))', block)
            
            # Bỏ phần header của Điều (đoạn text trước Khoản 1)
            header_text = khoan_blocks.pop(0) 

            for k_block in khoan_blocks:
                k_block = k_block.strip()
                if not k_block: continue

                # Extract thông tin Khoản
                k_match = re.match(r'(?:Khoản\s+(\d+)|(\d{1,2})\.\s)', k_block)
                khoan_num = int(k_match.group(1) or k_match.group(2)) if k_match else None
                
                # Lấy dòng đầu tiên của Khoản (thường chứa mức phạt)
                khoan_header = k_block.split('\n')[0]

                # BƯỚC 3: Tách thành từng ĐIỂM (a, b, c, ...)
                # Điểm nằm bên trong Khoản
                diem_blocks = re.split(r'(?=\n\s*[a-zđ]\)\s)', k_block)

                if len(diem_blocks) <= 1:
                    # Khoản này không có Điểm nhỏ -> Lưu nguyên Khoản
                    full_txt = f"{dieu_header}\n{k_block}"
                    chunks.append(self._make_chunk(full_txt, file_path.name, dieu_num, dieu_title, khoan_num, None))
                else:
                    # Bỏ phần text mở đầu của Khoản (đoạn 'Phạt tiền từ...') để nối vào từng Điểm
                    khoan_intro = diem_blocks.pop(0) 
                    
                    for d_block in diem_blocks:
                        d_block = d_block.strip()
                        # Extract thông tin Điểm (a, b, c)
                        diem_match = re.match(r'([a-zđ])\)', d_block)
                        diem_label = diem_match.group(1) if diem_match else None
                        
                        # CONTEXT FLATTENING: Nối Tiêu đề Điều + Mức phạt của Khoản + Nội dung Điểm
                        flattened_content = f"{dieu_header}\n{khoan_intro}\n{d_block}"
                        
                        chunks.append(self._make_chunk(
                            content=flattened_content,
                            source=file_path.name,
                            dieu_num=dieu_num,
                            dieu_title=dieu_title,
                            khoan_num=khoan_num,
                            diem_label=diem_label
                        ))

        return chunks

    def _make_chunk(self, content, source, dieu_num, dieu_title, khoan_num, diem_label):
        # Tạo bản sạch để Embedding
        emb_content = self._clean_for_embedding(content)
        
        # Mapping thẩm quyền cơ bản (Dựa trên Điều 41/43)
        authorities = ["Cảnh sát giao thông", "Chủ tịch UBND"]
        if "đô thị" in content.lower() or "vỉa hè" in content.lower():
            authorities.append("Cảnh sát trật tự")

        return {
            "raw_content": content, # Dùng để Bot hiển thị kết quả
            "embedding_content": emb_content, # Dùng để tạo Vector
            "metadata": {
                "source": source,
                "dieu_num": dieu_num,
                "khoan_num": khoan_num,
                "diem": diem_label,
                "article_title": dieu_title,
                "vehicle_types": self._extract_vehicles(content),
                "violation_tags": self._extract_violations(content),
                "penalty_min": self._extract_penalty(content, "min"),
                "penalty_max": self._extract_penalty(content, "max"),
                "point_deduction": self._extract_point_deduction(content),
                "authorities": authorities
            }
        }

    def _extract_point_deduction(self, text):
        """Trích xuất số điểm bị trừ nếu có"""
        match = re.search(r'trừ\s+điểm\s+giấy\s+phép\s+lái\s+xe\s+(\d+)\s+điểm', text, re.I)
        return int(match.group(1)) if match else 0

    def _extract_vehicles(self, text):
        """Trích xuất loại phương tiện được đề cập trong văn bản"""
        vehicle_map = {
            "xe mô tô": "mô tô",
            "xe gắn máy": "gắn máy",
            "xe máy": "gắn máy",
            "xe ô tô": "ô tô",
            "ô tô": "ô tô",
            "xe tải": "ô tô",
            "xe khách": "ô tô",
            "xe con": "ô tô",
            "xe đạp điện": "xe đạp điện",
            "xe đạp máy": "xe đạp điện",
            "xe đạp": "xe đạp",
            "máy kéo": "máy kéo",
            "xe ba bánh": "xe ba bánh",
        }
        found = set()
        text_lower = text.lower()
        for keyword, vehicle_type in vehicle_map.items():
            if keyword in text_lower:
                found.add(vehicle_type)
        return list(found)

    def _extract_violations(self, text):
        """Trích xuất nhãn loại vi phạm"""
        violation_map = {
            "nồng độ cồn": "nong_do_con",
            "ma túy": "ma_tuy",
            "tốc độ": "toc_do",
            "vượt tốc": "toc_do",
            "mũ bảo hiểm": "mu_bao_hiem",
            "đèn đỏ": "den_do",
            "tín hiệu": "tin_hieu",
            "làn đường": "lan_duong",
            "vượt xe": "vuot_xe",
            "giấy phép lái xe": "gplx",
            "bằng lái": "gplx",
            "đăng ký xe": "dang_ky",
            "bảo hiểm": "bao_hiem",
            "điện thoại": "dien_thoai",
            "dừng đỗ": "dung_do",
            "đỗ xe": "dung_do",
            "tải trọng": "tai_trong",
            "chở người": "cho_nguoi",
        }
        found = set()
        text_lower = text.lower()
        for keyword, tag in violation_map.items():
            if keyword in text_lower:
                found.add(tag)
        return list(found)

    def _extract_penalty(self, text, kind):
        """Trích xuất mức phạt min hoặc max (đơn vị: đồng)"""
        def parse_amount(s):
            return int(s.replace('.', '').replace(',', ''))

        # Pattern: "phạt tiền từ X đồng đến Y đồng"
        match = re.search(
            r'phạt tiền từ\s+([\d\.]+)\s*(?:đồng)?\s*đến\s+([\d\.]+)\s*đồng',
            text, re.I
        )
        if match:
            return parse_amount(match.group(1)) if kind == "min" else parse_amount(match.group(2))

        # Pattern: "phạt tiền X đồng" (mức cố định)
        match = re.search(r'phạt tiền\s+([\d\.]+)\s*đồng', text, re.I)
        if match:
            return parse_amount(match.group(1))

        return None

    def run(self):
        all_chunks = []
        txt_files = list(self.input_folder.glob("*.txt"))
        for txt_path in txt_files:
            file_chunks = self.process_file(txt_path)
            all_chunks.extend(file_chunks)
            print(f"  {txt_path.name}: {len(file_chunks)} chunks")

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=4)
        print(f"\n🚀 Hoàn thành! Đã tạo {len(all_chunks)} hạt dữ liệu (Atomic Chunks).")

if __name__ == "__main__":
    chunker = LegalChunker(
        input_folder="D:\\trafficChatbot\\rag_app\\data_pipeline\\cleaned_data",
        output_file="D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json"
    )
    chunker.run()