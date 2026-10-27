from django.core.management.base import BaseCommand, CommandError

from safety.telegram_link import create_link_for_contact
from safety.telegram_notify import (
    TelegramNotifyError,
    get_bot_info,
    is_enabled,
    send_message,
    send_safety_alert,
    set_webhook,
)
from safety.models import TrustedContact


class Command(BaseCommand):
    help = "Teste le bot Telegram Bokengi (getMe, envoi, webhook)."

    def add_arguments(self, parser):
        parser.add_argument("--get-me", action="store_true", help="Affiche les infos du bot.")
        parser.add_argument(
            "--set-webhook",
            metavar="URL",
            help="Enregistre le webhook (ex. https://bokengi.jej-tech.com/api/webhooks/telegram/).",
        )
        parser.add_argument("--chat-id", help="chat_id destinataire pour un test d'envoi.")
        parser.add_argument(
            "--body",
            default="Test Bokengi Telegram ✅",
            help="Corps du message texte.",
        )
        parser.add_argument(
            "--kind",
            choices=["sos", "trip", "checkin", "checkin_missed", "text"],
            default="text",
            help="Type d'alerte sécurité simulée.",
        )
        parser.add_argument(
            "--contact-id",
            type=int,
            help="ID TrustedContact — génère un lien /start pour liaison.",
        )

    def handle(self, *args, **options):
        if not is_enabled():
            raise CommandError(
                "Telegram désactivé. Définis TELEGRAM_ENABLED=true et TELEGRAM_BOT_TOKEN dans .env."
            )

        if options["get_me"]:
            info = get_bot_info()
            self.stdout.write(self.style.SUCCESS(f"Bot OK: @{info.get('username')} ({info.get('first_name')})"))
            self.stdout.write(f"id={info.get('id')}")

        if options["set_webhook"]:
            from django.conf import settings

            secret = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None) or "").strip()
            result = set_webhook(url=options["set_webhook"], secret_token=secret)
            self.stdout.write(self.style.SUCCESS(f"Webhook configuré: {result}"))

        if options["contact_id"]:
            contact = TrustedContact.objects.filter(id=options["contact_id"]).first()
            if not contact:
                raise CommandError(f"Contact {options['contact_id']} introuvable.")
            link = create_link_for_contact(contact)
            self.stdout.write(self.style.SUCCESS("Lien de liaison généré :"))
            self.stdout.write(f"  token={link['token']}")
            self.stdout.write(f"  url={link['link_url']}")
            self.stdout.write(f"  expire={link['expires_at']}")

        chat_id = options.get("chat_id")
        if chat_id:
            kind = options["kind"]
            try:
                if kind == "text":
                    msg_id = send_message(chat_id=chat_id, text=options["body"])
                    self.stdout.write(self.style.SUCCESS(f"Message envoyé id={msg_id}"))
                else:
                    ok = send_safety_alert(
                        chat_id=chat_id,
                        kind=kind,
                        contact_name="Contact test",
                        initiator_name="Bokengi Test",
                        track_url="https://bokengi.jej-tech.com/suivi/demo",
                        extra={"dest_label": "Gombe", "duration_minutes": 30},
                    )
                    if not ok:
                        raise CommandError("Envoi échoué (voir logs).")
                    self.stdout.write(self.style.SUCCESS(f"Alerte {kind} envoyée à {chat_id}"))
            except TelegramNotifyError as exc:
                raise CommandError(str(exc)) from exc

        if not any(
            [
                options["get_me"],
                options["set_webhook"],
                options["contact_id"],
                chat_id,
            ]
        ):
            raise CommandError(
                "Indiquez au moins une action : --get-me, --set-webhook URL, --chat-id ID, --contact-id ID."
            )
