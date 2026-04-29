# Traffic Chatbot — CLAUDE.md

Chatbot tư vấn luật giao thông Việt Nam, dùng kiến trúc RAG (Retrieval-Augmented Generation).

---

## Tech Stack

| Layer | Công nghệ |
|---|---|
| Backend | Django 5.2 |
| Database | PostgreSQL (Supabase cloud) + pgvector extension |
| Embedding | `keepitreal/vietnamese-sbert` (768 chiều, SentenceTransformer) |
| LLM | Qwen/Qwen2.5-7B-Instruct via Hugging Face Inference API |
| Full-text search | PostgreSQL tsvector/tsquery (`simple` config) |
| Frontend | Vanilla HTML/CSS/JS, markdown render client-side |

---

## Cấu trúc thư mục

```
trafficChatbot/
├── rag_app/                    # App chính (đang dùng)
│   ├── data_pipeline/
│   │   ├── 1_clearer.py        # Bước 1: Trích xuất PDF, làm sạch text
│   │   ├── 2_chunker.py        # Bước 2: Chia chunk theo cấu trúc pháp lý
│   │   ├── 3_embed.py          # Bước 3: Tạo embedding + nạp vào DB
│   │   ├── raw_data/           # PDF đầu vào
│   │   ├── cleaned_data/       # Text đã làm sạch
│   │   └── final_chunks.json   # Chunks trước khi embed
│   ├── migrations/             # Django migrations (0001→0005)
│   ├── static/rag_app/         # chat.css, chat.js
│   ├── templates/rag_app/      # chat.html
│   ├── models.py               # TrafficLawChunk model
│   ├── services.py             # Hybrid search + LLM orchestration
│   ├── views.py                # API endpoints
│   ├── urls.py                 # URL routing
│   └── prompts.py              # System prompt + user prompt builder
├── chat_app/                   # App cũ (legacy, không dùng nữa)
├── traffic_chatbot/            # Django project config
│   ├── settings.py
│   └── urls.py
├── manage.py
├── requirements.txt
├── .env                        # DB credentials, API keys
└── docker-compose.yml          # PostgreSQL + pgvector local
```

---

## Database Schema

**Bảng: `traffic_law_chunks`**

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | BIGINT PK | Auto |
| `content` | TEXT | Raw text gốc (để hiển thị) |
| `embedding` | vector(768) | Dense vector từ vietnamese-sbert |
| `search_vector` | TSVECTOR | BM25 full-text index (GIN index) |
| `source` | VARCHAR(255) | Tên file nguồn (VD: `168_2024_ND-CP_...txt`) |
| `dieu_num` | INT | Số điều |
| `khoan_num` | INT | Số khoản |
| `diem` | VARCHAR(10) | Điểm chữ cái (a, b, c...) |
| `dieu_title` | VARCHAR(500) | Tiêu đề điều |
| `vehicle_types` | JSONB | Danh sách loại phương tiện áp dụng |
| `violation_tags` | JSONB | Tags vi phạm (nong_do_con, toc_do...) |
| `penalty_min` | BIGINT | Mức phạt tối thiểu (VNĐ) |
| `penalty_max` | BIGINT | Mức phạt tối đa (VNĐ) |
| `point_deduction` | INT | Số điểm trừ bằng lái |
| `authorities` | JSONB | Cơ quan có thẩm quyền xử phạt |

---

## API Endpoints

| Method | Route | Chức năng |
|---|---|---|
| GET | `/` | Render giao diện chat |
| POST | `/api/chat/` | Nhận câu hỏi → trả lời (JSON) |
| GET | `/api/history/` | Lấy lịch sử chat từ session |
| POST | `/api/history/save/` | Lưu/cập nhật hội thoại vào session |
| POST | `/api/history/clear/` | Xóa toàn bộ lịch sử |

**Request `/api/chat/`:**
```json
{ "question": "string", "history": [{"question":"...","answer":"...","sources":[...]}] }
```

**Response:**
```json
{ "success": true, "answer": "markdown string", "sources": ["168_2024_ND-CP_..."] }
```

---

## Luồng xử lý (RAG Pipeline)

```
Câu hỏi người dùng
    ↓
Encode → vector 768 chiều (vietnamese-sbert)
    ↓
Hybrid Search (_hybrid_search trong services.py):
    ├─ Dense vector search  → top 20 (cosine distance, pgvector)
    ├─ BM25 full-text       → top 20 (tsvector/tsquery, 'simple' config)
    └─ Reciprocal Rank Fusion (k=60) → top 5 chunks
    ↓
Xây context RAG: "[Điều X - source]\ncontent"
    ↓
Build user prompt (prompts.py): context + lịch sử 3 lượt gần nhất
    ↓
Gọi LLM: Qwen2.5-7B (HuggingFace API, max_tokens=512, temp=0.1)
    ↓
Trả JSON: { answer, sources }
```

### Công thức RRF
```
score = 1/(60 + rank_vector) + 1/(60 + rank_bm25)
```
Lấy top-5 chunks có điểm cao nhất sau khi cộng hai nhánh.

---

## Data Pipeline (ETL)

Chạy theo thứ tự khi cập nhật dữ liệu pháp luật mới:

### Bước 1 — `1_clearer.py`
- Input: PDF trong `raw_data/`
- Dùng `pdfplumber` trích xuất text
- Làm sạch: chuẩn hóa Unicode, xóa OCR lỗi, xóa header/footer/chữ ký
- Output: `cleaned_data/*.txt`

### Bước 2 — `2_chunker.py`
- Input: `cleaned_data/*.txt`
- Tách theo cấu trúc: **Điều → Khoản → Điểm**
- Context flattening: mỗi chunk ghép tiêu đề Điều + mức phạt Khoản + nội dung Điểm
- Trích xuất metadata: phương tiện, vi phạm, mức phạt, điểm trừ
- Tạo `embedding_content` (đã xóa các cụm "trừ các hành vi..." để giảm nhiễu)
- Output: `final_chunks.json`

### Bước 3 — `3_embed.py`
- Input: `final_chunks.json`
- Tạo vector embedding (batch 64, vietnamese-sbert)
- `bulk_create()` vào PostgreSQL
- Sau mỗi batch: `UPDATE search_vector = to_tsvector('simple', content)`
- Xóa dữ liệu cũ theo `source` trước khi insert lại (idempotent)

---

## System Prompt (prompts.py)

LLM được cấu hình xử lý 7 loại câu hỏi:

1. **Phạt/Vi phạm** → Dạng mục: mức phạt + điểm trừ + cơ quan
2. **Quy định/Điều kiện** → Trả lời thẳng + liệt kê chi tiết
3. **Thủ tục/Quy trình** → Các bước đánh số + thời hạn
4. **So sánh** → Bảng + tổng kết
5. **Câu hỏi mơ hồ** → Trả lời chung + hỏi lại làm rõ
6. **Xác nhận ("Đúng không?")** → Xác nhận + trích dẫn đầy đủ
7. **Không có dữ liệu** → 1 câu: "Dữ liệu chưa có..."

Lịch sử chat: gửi 3 lượt gần nhất (mỗi lượt tối đa 150 ký tự).

---

## Session Management

- Lưu trong Django session (server-side)
- Tối đa 50 hội thoại (FIFO)
- Mỗi hội thoại là 1 mảng `[{question, answer, sources}]`
- Frontend tải lịch sử khi load trang, sidebar hiển thị danh sách

---

## Environment Variables

```
DB_HOST=db.yryslfufmltohwaczsmy.supabase.co
DB_USER=postgres
DB_PASSWORD=...
DB_NAME=postgres
DB_PORT=5432
SECRET_KEY=...
DEBUG=True
HUGGINGFACEHUB_API_KEY=hf_...
```

---

## Lệnh hay dùng

```bash
# Chạy server
python manage.py runserver

# Migrate DB
python manage.py migrate

# Chạy lại toàn bộ pipeline ETL
python rag_app/data_pipeline/1_clearer.py
python rag_app/data_pipeline/2_chunker.py
python rag_app/data_pipeline/3_embed.py

# Tạo migration mới sau khi sửa models.py
python manage.py makemigrations
```

---

## Lưu ý kiến trúc

- `chat_app/` là app cũ, **không dùng nữa** — chỉ `rag_app/` là active.
- `embedding_content` (chunk đã lọc nhiễu) dùng để tạo vector; `raw_content` dùng để hiển thị — hai trường khác nhau.
- BM25 dùng config `'simple'` (không stemming) — phù hợp tiếng Việt vì từ đã tách bằng khoảng trắng.
- `penalty_min/max`, `vehicle_types`, `violation_tags` được lưu nhưng **chưa được dùng để filter** trong search — tiềm năng cải thiện trong tương lai.
- Không có authentication — phù hợp demo, cần thêm nếu deploy production.

---

## Phân tích hiệu quả Semantic Search

### Tổng quan kiến trúc tìm kiếm

Hệ thống dùng **Hybrid Search = Dense Vector + BM25 Full-text**, kết hợp bằng **Reciprocal Rank Fusion (RRF)**. Đây là cách tiếp cận phù hợp cho văn bản pháp luật vì hai loại câu hỏi thường gặp có đặc điểm trái ngược nhau:

| Loại câu hỏi | Ví dụ | Phương pháp phù hợp |
| --- | --- | --- |
| Ngữ nghĩa / Diễn đạt khác | "uống rượu lái xe bị phạt gì?" | Dense Vector |
| Chính xác / Từ khóa cụ thể | "Điều 6 khoản 3 NĐ 168" | BM25 |
| Kết hợp cả hai | "vi phạm nồng độ cồn theo Điều 5" | RRF (cả hai) |

---

### Đánh giá từng lớp

#### 1. Làm sạch văn bản (`1_clearer.py`) — Nền tảng chất lượng

**Mạnh:**

- Loại bỏ hoàn toàn boilerplate pháp lý (quốc hiệu, ngày ký, chữ ký, "Căn cứ")
- Chuẩn hóa Unicode NFC — tránh lỗi so sánh chuỗi tiếng Việt (ví dụ: `ă` tổ hợp vs `ă` precomposed)
- Fix lỗi OCR: số tiền bị tách (`100 000` → `100000`), chữ `l` nhầm thành `1`
- Xóa cụm dẫn chiếu rác ("trừ các hành vi vi phạm quy định tại...") ngay từ đây, giảm nhiễu cho cả BM25 lẫn vector

**Yếu:**

- Regex cứng — nếu PDF mới có cấu trúc khác (bảng, cột đôi, footnote) có thể bị sót hoặc xóa nhầm nội dung
- Không có bước kiểm tra sau làm sạch (validation)

---

#### 2. Chiến lược Chunking (`2_chunker.py`) — Ảnh hưởng lớn nhất đến retrieval

**Context Flattening** là điểm mạnh quan trọng nhất:

```
Thay vì lưu:
  chunk = "a) Không vượt 50mg/100ml máu → phạt 2-3 triệu"

Hệ thống lưu:
  chunk = "Điều 5. Vi phạm quy định về nồng độ cồn
            6. Phạt tiền từ 2.000.000 đến 3.000.000 đồng đối với xe mô tô
            a) Không vượt 50mg/100ml máu → phạt 2-3 triệu"
```

**Lý do hiệu quả:** Embedding của điểm `a)` đơn lẻ sẽ thiếu ngữ cảnh (không biết điều nào, mức phạt bao nhiêu). Sau flattening, vector của chunk đã chứa đầy đủ thông tin → tìm kiếm chính xác hơn nhiều.

**Hai trường content tách biệt:**

| Trường | Nội dung | Dùng để |
| --- | --- | --- |
| `embedding_content` | Đã xóa "trừ các hành vi...", "quy định tại..." | Tạo vector (ít nhiễu) |
| `raw_content` | Văn bản gốc đầy đủ | Hiển thị cho người dùng |

Cách tách này đảm bảo vector đại diện cho **ý nghĩa cốt lõi** của điều khoản, không bị kéo lệch bởi các cụm dẫn chiếu không liên quan.

---

#### 3. Dense Vector Search — Hiểu ngữ nghĩa tiếng Việt

**Model:** `keepitreal/vietnamese-sbert` (768 chiều)

- Được fine-tune riêng cho tiếng Việt trên tập dữ liệu sentence similarity
- Hiểu được các cách diễn đạt đồng nghĩa: "nồng độ cồn" ≈ "uống rượu bia" ≈ "say xỉn"
- Cosine distance: phù hợp vì SBERT normalize embedding về unit sphere → cosine = dot product

**Trường hợp hoạt động tốt:**

- Câu hỏi dùng ngôn ngữ thông thường khác với từ ngữ pháp lý
- Câu hỏi mơ hồ, thiếu từ khóa chính xác
- Follow-up questions ("còn với xe máy thì sao?")

**Trường hợp yếu:**

- Câu hỏi tra cứu số điều cụ thể ("Điều 21 nói gì?") — vector không nhạy với số
- Mức phạt chính xác ("phạt đúng 4 triệu") — số tiền cụ thể dễ bị miss
- Từ viết tắt pháp lý ("NĐ 168", "GPLX") nếu không có trong training data

**Threshold đã điều chỉnh:** Bỏ giới hạn `distance < 0.5` cứng, lấy top-20 để RRF quyết định — tránh bỏ sót chunk tốt ở vị trí 6-20.

---

#### 4. BM25 Full-text Search — Bù đắp điểm yếu của Vector

**Cấu hình:** PostgreSQL `to_tsvector('simple', content)` + GIN index

`simple` config: chỉ lowercase + tách từ theo khoảng trắng, không stemming. Phù hợp tiếng Việt vì:

- Tiếng Việt là ngôn ngữ đơn lập — mỗi từ đã là đơn vị nghĩa độc lập
- Không cần stemming như tiếng Anh ("running" → "run")
- "nồng độ cồn" sẽ match chunk có đúng 3 từ này

**Trường hợp hoạt động tốt:**

- Tra cứu số điều, khoản ("Điều 5", "khoản 3")
- Mức tiền cụ thể ("4.000.000", "2 triệu")
- Từ khóa pháp lý đặc thù ("tước GPLX", "tịch thu phương tiện")
- Tên văn bản ("NĐ 168/2024", "Luật Giao thông")

**Trường hợp yếu:**

- Câu hỏi paraphrase: "bị mất bằng" ≠ "tước GPLX" trong BM25
- Câu ngắn, ít từ → BM25 rank không phân biệt được nhiều chunk

---

#### 5. Reciprocal Rank Fusion (RRF) — Bộ kết hợp

```
score(chunk) = 1/(60 + rank_vector) + 1/(60 + rank_bm25)
```

**Tại sao k=60 là mặc định tốt:**

- k nhỏ (< 10): chunk ở top 1 được ưu ái quá mức, chunk top 10 bị bỏ qua
- k=60: cân bằng — chunk rank 1 được 1/61 ≈ 0.016, chunk rank 20 được 1/80 ≈ 0.012 (chênh lệch vừa phải)
- Chunk xuất hiện trong **cả hai** kết quả sẽ được cộng điểm từ 2 nguồn → đúng là chunk quan trọng

**Ví dụ cụ thể:**

| Chunk | Rank vector | Rank BM25 | RRF Score |
|---|---|---|---|
| Chunk A (match cả hai) | 3 | 2 | 1/63 + 1/62 = **0.032** |
| Chunk B (chỉ vector, rank 1) | 1 | không có | 1/61 = **0.016** |
| Chunk C (chỉ BM25, rank 1) | không có | 1 | 1/61 = **0.016** |

→ Chunk A thắng dù không đứng đầu ở bất kỳ nhánh nào — đây là hành vi đúng.

---

### So sánh: Trước và Sau khi chuyển sang Hybrid

| Tình huống | Dense Only (cũ) | Hybrid RRF (mới) |
|---|---|---|
| "uống rượu lái xe" | ✅ Tìm được (ngữ nghĩa) | ✅ Tốt hơn (vector + BM25 cùng match) |
| "Điều 5 khoản 6" | ❌ Thường miss (số không có nghĩa vector) | ✅ BM25 bù vào |
| "phạt 4 triệu" | ❌ Vector không nhạy với số tiền | ✅ BM25 match chính xác |
| "tước GPLX bao lâu" | ⚠️ Phụ thuộc threshold 0.5 | ✅ Không có threshold cứng |
| Câu mơ hồ ngắn | ✅ Vector xử lý tốt | ✅ Giữ nguyên ưu điểm |
| Câu hỏi diễn đạt khác | ✅ Vector mạnh | ✅ Giữ nguyên ưu điểm |

---

### Điểm yếu còn tồn tại

1. **Không word-segment tiếng Việt:** `simple` config tách theo khoảng trắng — "xe máy" vs "xemáy" sẽ miss nhau. Giải pháp nâng cấp: tích hợp `pyvi` hoặc `underthesea` để segment trước khi index.

2. **Metadata chưa được dùng để filter:** `vehicle_types`, `violation_tags`, `penalty_min/max` đang bị bỏ phí. Nếu dùng được ("tôi đi xe máy, vượt đèn đỏ"), có thể filter trước → giảm nhiễu từ 20 xuống ~5 candidates trước khi RRF.

3. **Không có re-ranking:** Sau RRF top-5, không có cross-encoder để re-rank lần 2. Cross-encoder mạnh hơn bi-encoder nhưng chậm — có thể thêm nếu cần độ chính xác cao hơn.

4. **LLM context cố định 5 chunks:** Nếu câu hỏi cần nhiều điều khoản khác nhau (VD: "so sánh xe máy và ô tô vi phạm nồng độ cồn"), 5 chunks có thể không đủ.

5. **BM25 không hiểu đồng nghĩa:** "mất bằng lái" ≠ "tước giấy phép lái xe" với BM25 — vector phải bù lại, nhưng nếu vector cũng miss thì cả hệ thống miss.
