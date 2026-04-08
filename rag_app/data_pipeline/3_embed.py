import os
import django
import json
import sys
from sentence_transformers import SentenceTransformer

project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'traffic_chatbot.settings')
django.setup()

from rag_app.models import TrafficLawChunk


class LegalEmbedder:
    def __init__(self, model_name="keepitreal/vietnamese-sbert"):
        print(" Đang tải model")
        self.model = SentenceTransformer(model_name)

    def run(self, json_file):
        if not os.path.exists(json_file):
            print(f" Không tìm thấy file {json_file}")
            return

        with open(json_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        print(f"Bắt đầu nạp {len(chunks)} chunks vào Database...")

        # 1. XỬ LÝ TRÙNG LẶP: Xóa dữ liệu cũ dựa trên tên file (source)
        # Cách này giúp bạn nạp đi nạp lại mà không bị nhân đôi dữ liệu
        sources = list(set([c['source'] for c in chunks]))
        for src in sources:
            deleted_count = TrafficLawChunk.objects.filter(source=src).delete()
            print(f"Đã xóa {deleted_count[0]} bản ghi cũ của file: {src}")

        # 2. EMBEDDING & SAVE
        for  item in chunks:
            content = item['content']
            source = item['source']

            # Biến văn bản thành dãy số (Vector)
            vector = self.model.encode(content).tolist()

            # Lưu vào Postgres qua Django Model
            TrafficLawChunk.objects.create(
                content=content,
                source=source,
                embedding=vector
            )

           

if __name__ == "__main__":
    embedder = LegalEmbedder()
    embedder.run("D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json")