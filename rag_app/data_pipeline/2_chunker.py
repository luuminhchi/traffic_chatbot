import os
import re
from pathlib import Path
import json

class LegalChunker:
    def __init__(self, input_folder, output_file):
        self.input_folder = Path(input_folder)
        self.output_file = output_file

    def process_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = []

        # ==================================================
        # BƯỚC 1: Tách thành từng ĐIỀU (unit cơ bản)
        # ==================================================
        # Split tại vị trí bắt đầu "Điều X"
        dieu_blocks = re.split(r'(?=\nĐiều\s+\d+)', content)

        for block in dieu_blocks:
            block = block.strip()
            if not block:
                continue

            # Extract số điều và tiêu đề
            dieu_match = re.match(r'(Điều\s+(\d+)[\.\:]?\s*(.*))', block)
            if not dieu_match:
                continue

            dieu_header = dieu_match.group(1).strip()  # "Điều 5. Vi phạm tốc độ"
            dieu_num    = int(dieu_match.group(2))     # 5
            dieu_title  = dieu_match.group(3).strip()  # "Vi phạm tốc độ"

            # ================================================
            # BƯỚC 2: Tách thành từng KHOẢN trong điều
            # ================================================
            # Khoản dạng "1." hoặc "Khoản 1"
            khoan_blocks = re.split(
                r'(?=\n(?:Khoản\s+\d+|\d{1,2}\.\s+[A-ZĐÀÁÂ]))',
                block
            )

            if len(khoan_blocks) <= 1:
                # Điều không có khoản → tạo 1 chunk cho cả điều
                chunks.append(self._make_chunk(
                    content=block,
                    source=file_path.name,
                    dieu_num=dieu_num,
                    dieu_title=dieu_title,
                    khoan_num=None,
                    chunk_type="article"
                ))
            else:
                for khoan_block in khoan_blocks:
                    khoan_block = khoan_block.strip()
                    if not khoan_block:
                        continue

                    # ✅ Fix lỗi 1 — bỏ qua nếu khoan_block chỉ là header điều
                    if khoan_block == dieu_header or khoan_block == block.split('\n')[0].strip():
                        continue

                    khoan_match = re.match(
                        r'(?:Khoản\s+(\d+)|(\d{1,2})\.\s)',
                        khoan_block
                    )
                    khoan_num = None
                    if khoan_match:
                        khoan_num = int(khoan_match.group(1) or khoan_match.group(2))

                    full_text = f"{dieu_header}\n{khoan_block}"

                    chunks.append(self._make_chunk(
                        content=full_text,
                        source=file_path.name,
                        dieu_num=dieu_num,
                        dieu_title=dieu_title,
                        khoan_num=khoan_num,
                        chunk_type="clause" if khoan_num else "article"
                    ))

        return chunks

    def _make_chunk(self, content, source, dieu_num,
                    dieu_title, khoan_num, chunk_type):
        """Tạo chunk kèm metadata đầy đủ"""
        return {
            "content": content,
            "metadata": {
                "source":       source,
                "dieu_num":     dieu_num,
                "dieu_title":   dieu_title,
                "khoan_num":    khoan_num,
                "chunk_type":   chunk_type,            
                "vehicle_types": self._extract_vehicles(content),
                "violation_tags": self._extract_violations(content),
                "penalty_min":  self._extract_penalty(content, "min"),
                "penalty_max":  self._extract_penalty(content, "max"),
                "has_revocation": "tước" in content.lower(),
            }
        }

    def _extract_vehicles(self, text):
        """Tag loại phương tiện"""
        tags = []
        if re.search(r'xe\s*(mô\s*tô|gắn\s*máy)', text, re.I):
            tags.append("mô tô")
        if re.search(r'xe\s*ô\s*tô', text, re.I):
            tags.append("ô tô")
        if re.search(r'xe\s*đạp', text, re.I):
            tags.append("xe đạp")
        if re.search(r'người\s*đi\s*bộ', text, re.I):
            tags.append("người đi bộ")
        return tags

    def _extract_violations(self, text):
        """Tag loại vi phạm"""
        tags = []
        mapping = {
            "tốc độ":       r'tốc\s*độ',
            "vượt đèn đỏ":  r'(đèn\s*đỏ|tín\s*hiệu\s*đèn)',
            "nồng độ cồn":  r'(nồng\s*độ\s*cồn|rượu|bia)',
            "không mũ bảo hiểm": r'mũ\s*bảo\s*hiểm',
            "sử dụng điện thoại": r'điện\s*thoại',
            "đi ngược chiều": r'ngược\s*chiều',
            "vượt xe":      r'vượt\s*xe',
            "tải trọng":    r'(tải\s*trọng|quá\s*tải)',
        }
        for tag, pattern in mapping.items():
            if re.search(pattern, text, re.I):
                tags.append(tag)
        return tags

    def _extract_penalty(self, text, mode):
    # Match cả 2 format:
    # "từ 800.000 đến 1.000.000 đồng"       ← đồng chỉ ở cuối
    # "từ 800.000 đồng đến 1.000.000 đồng"  ← đồng xuất hiện 2 lần

        patterns = [
            # Format 1: đồng chỉ ở cuối — PHỔ BIẾN NHẤT
            r'từ\s+([\d][.\d]+)\s*đến\s+([\d][.\d]+)\s*(?:đồng|VNĐ|vnđ)',
            # Format 2: đồng xuất hiện 2 lần
            r'từ\s+([\d][.\d]+)\s*(?:đồng|VNĐ).*?đến\s+([\d][.\d]+)\s*(?:đồng|VNĐ)',
            # Format 3: dùng dấu phẩy
            r'từ\s+([\d][,\d]+)\s*đến\s+([\d][,\d]+)\s*(?:đồng|VNĐ|vnđ)',
        ]

        def parse_number(s):
            """800.000 hoặc 800,000 → 800000"""
            return int(s.replace('.', '').replace(',', ''))

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    all_mins = [parse_number(m[0]) for m in matches]
                    all_maxs = [parse_number(m[1]) for m in matches]
                    if mode == "min":
                        return min(all_mins)
                    else:
                        return max(all_maxs)
                except:
                    continue

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

        print(f"\nXong! {len(all_chunks)} chunks từ {len(txt_files)} files.")


if __name__ == "__main__":
    chunker = LegalChunker(
        input_folder="D:\\trafficChatbot\\rag_app\\data_pipeline\\cleaned_data",
        output_file="D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json"
    )
    chunker.run()