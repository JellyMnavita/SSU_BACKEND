from django.db import migrations, models


def migrate_police_users_to_gov(apps, schema_editor):
    TypeUser = apps.get_model("users", "TypeUser")
    User = apps.get_model("users", "User")

    try:
        police_type = TypeUser.objects.get(code_typeUser="POLICE")
    except TypeUser.DoesNotExist:
        return

    gov_type, _ = TypeUser.objects.get_or_create(
        code_typeUser="GOV",
        defaults={"description_typeUser": "Service gouvernemental"},
    )
    User.objects.filter(type_user=police_type).update(type_user=gov_type)
    police_type.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_user_account_tier"),
    ]

    operations = [
        migrations.RunPython(migrate_police_users_to_gov, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="typeuser",
            name="code_typeUser",
            field=models.CharField(
                choices=[
                    ("GOV", "Service gouvernemental"),
                    ("COMPANY", "Entreprise étrangère"),
                    ("ADMIN", "Administrateur principal"),
                    ("USER", "Utilisateur simple"),
                ],
                max_length=10,
                unique=True,
            ),
        ),
    ]
