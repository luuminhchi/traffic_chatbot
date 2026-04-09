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
    def __init__(self, model_name="keepitreal/vietnamese-sbert", batch_size=64):
        self.model = SentenceTransformer(model_name)
        self.batch_size = batch_size

    def run(self, json_file):
        if not os.path.exists(json_file):
            print(f"Không tìm thấy file {json_file}")
            return

        with open(json_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        print(f"Bắt đầu nạp {len(chunks)} chunks...")

        # Xóa dữ liệu cũ theo source
        sources = list(set([c['metadata']['source'] for c in chunks]))
        for src in sources:
            deleted = TrafficLawChunk.objects.filter(source=src).delete()
            print(f"Đã xóa {deleted[0]} bản ghi cũ: {src}")

        # Batch embedding — nhanh hơn ~10x so với từng cái
        total = len(chunks)
        for i in range(0, total, self.batch_size):
            batch = chunks[i : i + self.batch_size]
            
            # Encode cả batch 1 lần
            contents = [item['content'] for item in batch]
            vectors = self.model.encode(
                contents,
                batch_size=self.batch_size,
                show_progress_bar=False
            ).tolist()

            # Tạo objects với đầy đủ metadata
            objects = []
            for item, vector in zip(batch, vectors):
                meta = item['metadata']
                objects.append(TrafficLawChunk(
                    content        = item['content'],
                    embedding      = vector,
                    source         = meta.get('source', ''),
                    dieu_num       = meta.get('dieu_num'),
                    dieu_title     = meta.get('dieu_title', ''),
                    khoan_num      = meta.get('khoan_num'),
                    chunk_type     = meta.get('chunk_type', 'article'),
                    vehicle_types  = meta.get('vehicle_types', []),
                    violation_tags = meta.get('violation_tags', []),
                    penalty_min    = meta.get('penalty_min'),
                    penalty_max    = meta.get('penalty_max'),
                    has_revocation = meta.get('has_revocation', False),
                ))

            # 1 INSERT duy nhất cho cả batch
            TrafficLawChunk.objects.bulk_create(objects)
            print(f"  [{i + len(batch)}/{total}] đã embed xong")

        print(f"\nHoàn tất! {total} chunks trong DB.")


if __name__ == "__main__":
    embedder = LegalEmbedder(batch_size=64)
    embedder.run("D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json")