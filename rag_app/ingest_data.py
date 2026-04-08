import os
import django
import glob
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings


# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'traffic_chatbot.settings')
django.setup()

from rag_app.models import TrafficLawChunk

def ingest_pdf(filePath):
    loader = PyPDFLoader(filePath)
    pages = loader.load()

    # chunking
    text_spliter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50, 
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_spliter.split_documents(pages)

    modelname = "keepitreal/vietnamese-sbert"
    embedding = HuggingFaceEmbeddings(model_name=modelname)

    # TrafficLawChunk.objects.all().delete() # Xóa dữ liệu cũ trước khi thêm mới
    for chunk in chunks:
        vector = embedding.embed_documents([chunk.page_content])[0]

        # Lưu vào database
        TrafficLawChunk.objects.create(
            content = chunk.page_content,
            embedding = vector,
            metadata = {
                "page": chunk.metadata.get("page_number", None),
                "source": os.path.basename(filePath)
            },
            source = os.path.basename(filePath)
        )
if __name__ == "__main__":
    path = r'D:\trafficChatbot\Data\*.pdf'

    # Lấy danh sách tất cả các file khớp với mẫu
    files = glob.glob(path)
    if not files:
        print("Không tìm thấy file PDF để ingest.")
    else:
        for file in files:
            try:
                ingest_pdf(file)
                print(f"Đã ingest dữ liệu từ {os.path.basename(file)} thành công!")
            except Exception as e:
                print(f"Lỗi khi ingest {os.path.basename(file)}: {str(e)}")