from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_user_preferences_and_sessions"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account_tier",
            field=models.CharField(
                choices=[
                    ("NORMAL", "Normal"),
                    ("PRO", "Pro"),
                    ("PREMIUM", "Premium"),
                ],
                default="NORMAL",
                help_text="Forfait citoyen (Normal, Pro, Premium). Réservé aux comptes USER.",
                max_length=10,
            ),
        ),
    ]
