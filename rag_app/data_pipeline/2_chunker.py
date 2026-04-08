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
        current_dieu = ""
        current_khoan_phat = ""
        
        # Tách văn bản thành từng dòng để phân tích
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue

            # 1. Nhận diện ĐIỀU (Ví dụ: Điều 5. Xử phạt người điều khiển...)
            if re.match(r'^Điều\s+\d+', line):
                current_dieu = line
                current_khoan_phat = "" # Reset mức phạt khi sang điều mới
            
            # 2. Nhận diện KHOẢN chứa mức phạt (Ví dụ: Khoản 1. Phạt tiền từ...)
            elif re.match(r'^Khoản\s+\d+', line):
                current_khoan_phat = line
                # Đôi khi Khoản cũng là một hành vi độc lập, ta lưu nó thành 1 chunk luôn
                full_text = f"{current_dieu}\n{line}"
                chunks.append({"content": full_text, "source": file_path.name})

            # 3. Nhận diện ĐIỂM hành vi (Ví dụ: a) Không chấp hành...)
            elif re.match(r'^[a-zđ]\)', line):
                # TIÊM BỐI CẢNH: Ghép Điều + Khoản mức phạt + Điểm hành vi
                full_text = f"{current_dieu}\n{current_khoan_phat}\nHành vi vi phạm: {line}"
                chunks.append({
                    "content": full_text, 
                    "source": file_path.name
                })
            
            # 4. Các trường hợp bổ sung hoặc giải thích
            else:
                if current_dieu:
                    full_text = f"{current_dieu}\n{line}"
                    chunks.append({"content": full_text, "source": file_path.name})

        return chunks

    def run(self):
        all_chunks = []
        txt_files = list(self.input_folder.glob("*.txt"))
        
        for txt_path in txt_files:
            file_chunks = self.process_file(txt_path)
            all_chunks.extend(file_chunks)
            
        # Lưu kết quả ra file JSON để bước 3 (Embedding) sử dụng
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=4)
            
        print(f"Xong!{len(all_chunks)} chunks đã được tạo.")

if __name__ == "__main__":
    chunker = LegalChunker(
        input_folder="D:\\trafficChatbot\\rag_app\\data_pipeline\\cleaned_data",
        output_file="D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json"
    )
    chunker.run()