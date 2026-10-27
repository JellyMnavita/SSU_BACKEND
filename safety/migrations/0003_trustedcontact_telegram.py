from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("safety", "0002_trustedcontact_email_safetyalert"),
    ]

    operations = [
        migrations.AddField(
            model_name="trustedcontact",
            name="telegram_chat_id",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="trustedcontact",
            name="telegram_link_token",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="trustedcontact",
            name="telegram_link_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
