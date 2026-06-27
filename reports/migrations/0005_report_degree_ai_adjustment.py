from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0004_report_ai_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="user_degree_before_ai",
            field=models.CharField(
                blank=True,
                choices=[("F", "Faible"), ("M", "Moyen"), ("E", "Elevé")],
                default="",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_recommended_degree",
            field=models.CharField(
                blank=True,
                choices=[("F", "Faible"), ("M", "Moyen"), ("E", "Elevé")],
                default="",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="degree_adjusted_by_ai",
            field=models.BooleanField(default=False),
        ),
    ]
