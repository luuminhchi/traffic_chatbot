# rag_app/models.py
from django.db import models
from pgvector.django import VectorField
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

class TrafficLawChunk(models.Model):
    content = models.TextField()  # Lưu raw_content (bản gốc)
    embedding = VectorField(dimensions=768) # 768 chiều cho vietnamese-sbert
    search_vector = SearchVectorField(null=True, blank=True)  # BM25 full-text index
    source = models.CharField(max_length=255)
    dieu_num = models.IntegerField(null=True)
    khoan_num = models.IntegerField(null=True)
    diem = models.CharField(max_length=10, null=True, blank=True) # Mới
    dieu_title = models.CharField(max_length=500)
    vehicle_types = models.JSONField(default=list)
    violation_tags = models.JSONField(default=list)
    penalty_min = models.BigIntegerField(null=True)
    penalty_max = models.BigIntegerField(null=True)
    point_deduction = models.IntegerField(default=0) # Mới
    authorities = models.JSONField(default=list) # Mới

    class Meta:
        db_table = 'traffic_law_chunks'
        indexes = [
            GinIndex(fields=['search_vector'], name='search_vector_gin_idx'),
        ]