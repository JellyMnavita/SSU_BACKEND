from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import TypeUser, User

# Un utilisateur de base par type
_USERS = [
    {
        "type_code": "ADMIN",
        "username": "admin_ssu",
        "email": "admin@ssu.cd",
        "password": "Admin@ssu2025",
        "phone_user": "+243810000001",
        "sexe_user": "M",
        "is_verified": True,
        "is_staff": True,
    },
    {
        "type_code": "GOV",
        "username": "gov_ssu",
        "email": "gouvernement@ssu.cd",
        "password": "Gov@ssu2025",
        "phone_user": "+243810000002",
        "sexe_user": "M",
        "is_verified": True,
        "is_staff": False,
    },
    {
        "type_code": "COMPANY",
        "username": "company_ssu",
        "email": "entreprise@ssu.cd",
        "password": "Company@ssu2025",
        "phone_user": "+243810000003",
        "sexe_user": "F",
        "is_verified": True,
        "is_staff": False,
    },
    {
        "type_code": "USER",
        "username": "user_ssu",
        "email": "utilisateur@ssu.cd",
        "password": "User@ssu2025",
        "phone_user": "+243810000004",
        "sexe_user": "M",
        "is_verified": True,
        "is_staff": False,
    },
]


class Command(BaseCommand):
    help = "Crée un utilisateur de base par type (ADMIN, GOV, COMPANY, USER)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime les utilisateurs seed avant de les recréer.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # S'assurer que les TypeUser existent
        type_descriptions = {
            "ADMIN": "Administrateur principal",
            "GOV": "Service gouvernemental",
            "COMPANY": "Entreprise étrangère",
            "USER": "Utilisateur simple",
        }
        for code, desc in type_descriptions.items():
            TypeUser.objects.get_or_create(
                code_typeUser=code,
                defaults={"description_typeUser": desc},
            )

        if options["clear"]:
            usernames = [u["username"] for u in _USERS]
            deleted, _ = User.objects.filter(username__in=usernames).delete()
            self.stdout.write(self.style.WARNING(f"Supprimé {deleted} utilisateur(s) seed."))

        created = 0
        skipped = 0

        for data in _USERS:
            if User.objects.filter(username=data["username"]).exists():
                self.stdout.write(f"  [SKIP] {data['username']} existe déjà.")
                skipped += 1
                continue

            type_user = TypeUser.objects.get(code_typeUser=data["type_code"])

            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"],
                type_user=type_user,
                phone_user=data["phone_user"],
                sexe_user=data["sexe_user"],
                is_verified=data["is_verified"],
                is_staff=data["is_staff"],
                agreementTermsUse_user=True,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] {user.username} ({data['type_code']}) — {data['email']} / mdp: {data['password']}"
                )
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nSeed users : {created} créé(s), {skipped} ignoré(s).")
        )
