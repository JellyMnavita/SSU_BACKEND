from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0007_report_ai_auto_moderation_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="external_source_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="URL de l'article source (signalements système).",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="reportaisettings",
            name="auto_ingest_news",
            field=models.BooleanField(
                default=False,
                help_text="Ingérer automatiquement les actualités sécurité (scraping → signalements source=S).",
            ),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="image_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="location_label",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="published_label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="reject_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="report",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scraped_article",
                to="reports.report",
            ),
        ),
        migrations.AddField(
            model_name="scrapedreport",
            name="source_site",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AlterField(
            model_name="scrapedreport",
            name="content",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="scrapedreport",
            name="title",
            field=models.CharField(max_length=300),
        ),
        migrations.AlterField(
            model_name="scrapedreport",
            name="url_source",
            field=models.URLField(max_length=500, unique=True),
        ),
        migrations.AlterModelOptions(
            name="scrapedreport",
            options={"ordering": ["-date_scraped"]},
        ),
    ]
