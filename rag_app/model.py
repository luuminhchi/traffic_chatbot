from django.db import models
from pgvector.django import VectorField

class TrafficLawChunk(models.Model):
    content = models.TextField()
    embedding = VectorField(dimensions=384) # Dùng cho model vietnamese-sbert
    metadata = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Law Chunk {self.id} - {self.source}"