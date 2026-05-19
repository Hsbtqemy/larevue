from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un email de test pour vérifier la configuration SMTP."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Adresse e-mail destinataire")

    def handle(self, *args, **options):
        to = options["email"]
        try:
            send_mail(
                subject="[Outil éditorial] Test de configuration SMTP",
                message=(
                    "Si vous recevez ce message, la configuration SMTP "
                    "fonctionne correctement.\n\n"
                    f"Backend : {settings.EMAIL_BACKEND}\n"
                    f"Expéditeur : {settings.DEFAULT_FROM_EMAIL}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to],
            )
        except Exception as exc:
            raise CommandError(f"Échec de l'envoi : {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Email de test envoyé à {to}"))
