from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0010_report_ai_reject_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="picture_sha256",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Empreinte SHA-256 de la photo (anti-doublon signalements).",
                max_length=64,
            ),
        ),
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(
                condition=models.Q(("picture_sha256__gt", "")),
                fields=("picture_sha256",),
                name="unique_report_picture_sha256",
            ),
        ),
    ]
