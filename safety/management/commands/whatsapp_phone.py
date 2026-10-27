from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from safety.whatsapp_api import (
    WhatsAppApiError,
    diagnose_access,
    list_phone_numbers,
    register_phone_number,
)


class Command(BaseCommand):
    help = (
        "Liste ou enregistre un numéro WhatsApp Cloud API (statut Meta « En attente »). "
        "Nécessite WHATSAPP_ACCESS_TOKEN et WHATSAPP_BUSINESS_ACCOUNT_ID dans .env."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list",
            action="store_true",
            help="Affiche les numéros et leurs Phone Number ID.",
        )
        parser.add_argument(
            "--register",
            action="store_true",
            help="Appelle l'API d'inscription Meta pour activer le numéro.",
        )
        parser.add_argument(
            "--phone-number-id",
            default="",
            help="Phone Number ID (sinon WHATSAPP_PHONE_NUMBER_ID du .env).",
        )
        parser.add_argument(
            "--pin",
            default="",
            help="PIN à 6 chiffres que vous choisissez (2FA Business). Pas le code SMS.",
        )
        parser.add_argument(
            "--waba-id",
            default="",
            help="WhatsApp Business Account ID (sinon variable .env).",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Diagnostique le token et les permissions Graph API.",
        )

    def handle(self, *args, **options):
        if options["debug"]:
            self._debug(options["waba_id"], options["phone_number_id"])
            return

        if options["list"]:
            self._list_phones(options["waba_id"])
            return

        if options["register"]:
            self._register(options["phone_number_id"], options["pin"])
            return

        raise CommandError("Indiquez --list, --register ou --debug.")

    def _debug(self, waba_id: str, phone_number_id: str) -> None:
        try:
            report = diagnose_access(
                waba_id=waba_id or None,
                phone_number_id=phone_number_id or None,
            )
        except WhatsAppApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("Diagnostic WhatsApp Cloud API")
        self.stdout.write(f"  token: {report['token_prefix']}")
        self.stdout.write(f"  api: {report['api_version']}")
        self.stdout.write(f"  waba_id: {report['waba_id']}")
        self.stdout.write(f"  phone_number_id: {report['phone_number_id']}")
        self.stdout.write("")

        for name, check in report["checks"].items():
            if check.get("ok"):
                self.stdout.write(self.style.SUCCESS(f"[OK] {name}"))
                data = check.get("data") or {}
                if name == "waba_phone_numbers":
                    for item in data.get("data") or []:
                        self.stdout.write(
                            f"    - {item.get('display_phone_number')} "
                            f"(id={item.get('id')}, status={item.get('status')})"
                        )
                elif name == "phone_number":
                    self.stdout.write(
                        f"    - {data.get('display_phone_number')} "
                        f"(verified_name={data.get('verified_name')})"
                    )
                elif name == "me":
                    self.stdout.write(f"    - id={data.get('id')} name={data.get('name')}")
                elif name == "waba":
                    self.stdout.write(
                        f"    - review={data.get('account_review_status')}"
                    )
            else:
                self.stdout.write(self.style.ERROR(f"[FAIL] {name}: {check.get('message')}"))
                if check.get("error_subcode") == 33:
                    self.stdout.write(
                        "    → Token sans accès à cet objet (mauvais token, "
                        "permissions manquantes, ou actif non assigné au WABA)."
                    )

        self.stdout.write("")
        self.stdout.write(
            "Si [FAIL] sur waba/phone_number : regénérez un token "
            "Utilisateur système avec whatsapp_business_management + "
            "whatsapp_business_messaging, et assignez App + compte WhatsApp."
        )

    def _list_phones(self, waba_id: str) -> None:
        try:
            phones = list_phone_numbers(waba_id or None)
        except WhatsAppApiError as exc:
            raise CommandError(str(exc)) from exc

        if not phones:
            self.stdout.write("Aucun numéro trouvé sur ce compte WABA.")
            return

        self.stdout.write(self.style.SUCCESS(f"{len(phones)} numéro(s) :"))
        for item in phones:
            self.stdout.write(
                f"- id={item.get('id')} | "
                f"display={item.get('display_phone_number')} | "
                f"verified_name={item.get('verified_name')} | "
                f"status={item.get('status')} | "
                f"quality={item.get('quality_rating')}"
            )

    def _register(self, phone_number_id: str, pin: str) -> None:
        pid = (phone_number_id or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or "").strip()
        pin_value = pin.strip()
        if not pid:
            raise CommandError(
                "Fournissez --phone-number-id ou WHATSAPP_PHONE_NUMBER_ID dans .env"
            )
        if not pin_value:
            raise CommandError(
                "Fournissez --pin=XXXXXX (6 chiffres que vous choisissez, pas le code SMS)."
            )

        try:
            result = register_phone_number(phone_number_id=pid, pin=pin_value)
        except WhatsAppApiError as exc:
            detail = exc.payload if exc.payload else str(exc)
            raise CommandError(f"Échec enregistrement WhatsApp : {exc}\n{detail}") from exc

        self.stdout.write(self.style.SUCCESS("Numéro enregistré via l'API Meta."))
        self.stdout.write(str(result))
        self.stdout.write(
            "\nConservez ce PIN en lieu sûr. Rafraîchissez le Gestionnaire WhatsApp "
            "(statut devrait passer de « En attente » à « Connecté »)."
        )
