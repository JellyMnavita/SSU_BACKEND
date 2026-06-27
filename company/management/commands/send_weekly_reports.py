"""Envoie manuellement les rapports hebdomadaires (test ou rattrapage)."""

from django.core.management.base import BaseCommand

from company.tasks import send_weekly_security_reports
from company.weekly_report import send_weekly_report_email
from users.models import User


class Command(BaseCommand):
    help = "Envoie le rapport hebdomadaire aux utilisateurs (weekly_report activé)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Limiter à un compte (ex. jej@ssu.cd)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule sans envoyer d'e-mail",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Déléguer à Celery",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip().lower()
        dry_run = options.get("dry_run", False)
        run_async = options.get("async", False)

        if run_async:
            result = send_weekly_security_reports.delay(dry_run=dry_run)
            self.stdout.write(self.style.SUCCESS(f"Tâche Celery lancée : {result.id}"))
            return

        if email:
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if not user:
                self.stderr.write(f"Utilisateur introuvable : {email}")
                return
            ok = send_weekly_report_email(user, dry_run=dry_run)
            label = "simulé" if dry_run else ("envoyé" if ok else "ignoré")
            self.stdout.write(self.style.SUCCESS(f"Rapport {label} pour {email}"))
            return

        stats = send_weekly_security_reports(dry_run=dry_run)
        self.stdout.write(self.style.SUCCESS(str(stats)))
