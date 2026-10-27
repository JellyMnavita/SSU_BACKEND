from django.core.management.base import BaseCommand, CommandError

from safety.twilio_whatsapp import (
    TwilioWhatsAppError,
    is_enabled,
    send_safety_alert,
    send_whatsapp_text,
)


class Command(BaseCommand):
    help = "Teste l'envoi WhatsApp via Twilio (sandbox ou numéro prod)."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Numéro destinataire (+243...)")
        parser.add_argument(
            "--body",
            default="Test Bokengi WhatsApp via Twilio ✅",
            help="Corps du message texte (sandbox).",
        )
        parser.add_argument(
            "--kind",
            choices=["sos", "trip", "checkin", "checkin_missed", "text"],
            default="text",
            help="Type d'alerte (utilise templates Content SID si configurés).",
        )

    def handle(self, *args, **options):
        if not is_enabled():
            raise CommandError(
                "Twilio WhatsApp désactivé. Définis TWILIO_WHATSAPP_ENABLED=true "
                "et TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM."
            )

        to_phone = options["to"]
        kind = options["kind"]
        try:
            if kind == "text":
                sid = send_whatsapp_text(to_phone=to_phone, body=options["body"])
                self.stdout.write(self.style.SUCCESS(f"Message envoyé sid={sid}"))
                return

            ok = send_safety_alert(
                to_phone=to_phone,
                kind=kind,
                contact_name="Contact test",
                initiator_name="Bokengi Test",
                track_url="https://bokengi.jej-tech.com/suivi/demo",
                extra={"dest_label": "Gombe", "duration_minutes": 30},
            )
            if not ok:
                raise CommandError("Envoi échoué (voir logs).")
            self.stdout.write(self.style.SUCCESS(f"Alerte {kind} envoyée à {to_phone}"))
        except TwilioWhatsAppError as exc:
            raise CommandError(str(exc)) from exc
