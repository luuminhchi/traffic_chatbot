import os
import django
import json
import sys
from sentence_transformers import SentenceTransformer

# Setup Django environment
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'traffic_chatbot.settings')
django.setup()

from rag_app.models import TrafficLawChunk
from django.contrib.postgres.search import SearchVector

class LegalEmbedder:
    def __init__(self, model_name="keepitreal/vietnamese-sbert", batch_size=64):
        print(f"Đang tải model {model_name} trên Nitro 5...")
        self.model = SentenceTransformer(model_name)
        self.batch_size = batch_size

    def run(self, json_file):
        if not os.path.exists(json_file):
            print(f"Không tìm thấy file {json_file}")
            return

        with open(json_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        print(f"Bắt đầu nạp {len(chunks)} chunks vào Supabase...")

        # Xóa dữ liệu cũ theo nguồn (tránh trùng lặp khi chạy lại)
        sources = list(set([c['metadata']['source'] for c in chunks]))
        for src in sources:
            deleted = TrafficLawChunk.objects.filter(source=src).delete()
            print(f"🗑️ Đã dọn dẹp {deleted[0]} bản ghi cũ của file: {src}")

        total = len(chunks)
        for i in range(0, total, self.batch_size):
            batch = chunks[i : i + self.batch_size]
            
            # ❗ QUAN TRỌNG: Lấy embedding_content để tạo Vector
            # Đây là bản đã lọc "trừ các hành vi..." giúp tìm kiếm chính xác hơn
            contents_to_embed = [item['embedding_content'] for item in batch]
            
            vectors = self.model.encode(
                contents_to_embed,
                batch_size=self.batch_size,
                show_progress_bar=False
            ).tolist()

            # Tạo danh sách objects để insert bulk
            objects = []
            for item, vector in zip(batch, vectors):
                meta = item['metadata']
                objects.append(TrafficLawChunk(
                    # Lưu bản gốc (raw_content) để hiển thị cho người dùng
                    content         = item['raw_content'], 
                    embedding       = vector,
                    source          = meta.get('source', ''),
                    dieu_num        = meta.get('dieu_num'),
                    khoan_num       = meta.get('khoan_num'),
                    diem            = meta.get('diem'), # Trường mới
                    dieu_title      = meta.get('article_title', ''),
                    vehicle_types   = meta.get('vehicle_types', []),
                    violation_tags  = meta.get('violation_tags', []),
                    penalty_min     = meta.get('penalty_min'),
                    penalty_max     = meta.get('penalty_max'),
                    point_deduction = meta.get('point_deduction', 0), # Trường mới
                    authorities     = meta.get('authorities', []),    # Trường mới
                ))

            # Thực hiện INSERT hàng loạt vào Supabase
            created = TrafficLawChunk.objects.bulk_create(objects)

            # Cập nhật search_vector (BM25 full-text index) cho batch vừa insert
            ids = [obj.id for obj in created]
            TrafficLawChunk.objects.filter(id__in=ids).update(
                search_vector=SearchVector('content', config='simple')
            )
            print(f"Tiến độ: [{i + len(batch)}/{total}] hạt dữ liệu đã 'lên mây'")

        print(f"\n Đã nạp thành công {total} chunks vào Database Vector.")

if __name__ == "__main__":
    embedder = LegalEmbedder(batch_size=64)
    # Đường dẫn tới file JSON đã tạo ở bước trước
    json_path = "D:\\trafficChatbot\\rag_app\\data_pipeline\\final_chunks.json"
    embedder.run(json_path)