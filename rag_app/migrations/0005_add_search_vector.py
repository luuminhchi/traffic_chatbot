from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations


def populate_search_vector(apps, schema_editor):
    # Dùng raw SQL để populate tsvector từ cột content
    schema_editor.execute(
        "UPDATE traffic_law_chunks SET search_vector = to_tsvector('simple', content)"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('rag_app', '0004_remove_trafficlawchunk_rag_app_tra_source_8ee628_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trafficlawchunk',
            name='search_vector',
            field=SearchVectorField(blank=True, null=True),
        ),
        migrations.RunPython(populate_search_vector, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='trafficlawchunk',
            index=GinIndex(fields=['search_vector'], name='search_vector_gin_idx'),
        ),
    ]
