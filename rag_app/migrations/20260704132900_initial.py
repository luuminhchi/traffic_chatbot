from django.db import migrations, models
from pgvector.django import VectorExtensions

class Migration(migrations.Migration):
    dependencies = []

    operations = [
        VectorExtensions(),
    ]