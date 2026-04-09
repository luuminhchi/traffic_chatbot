from django.db import models
from pgvector.django import VectorField
from django.utils import timezone


class TrafficLawChunk(models.Model):
    content     = models.TextField()
    source      = models.CharField(max_length=255, default='')
    
    dieu_num    = models.IntegerField(null=True)
    dieu_title  = models.TextField(null=True, blank=True)
    khoan_num   = models.IntegerField(null=True)
    chunk_type  = models.CharField(max_length=20, null=True)  # article | clause
    
    vehicle_types  = models.JSONField(default=list)
    violation_tags = models.JSONField(default=list)
    
    penalty_min    = models.BigIntegerField(null=True)
    penalty_max    = models.BigIntegerField(null=True)
    has_revocation = models.BooleanField(default=False)
    
    embedding   = VectorField(dimensions=768)  
    
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['dieu_num']),
        ]