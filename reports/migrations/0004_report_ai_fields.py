from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_alter_report_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="ai_incident_type",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_nlp_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_vision_results",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
