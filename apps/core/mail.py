from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_template_email(to: str, subject: str, template_base: str, context: dict) -> None:
    """Envoie un email HTML + texte brut à partir d'un nom de template de base."""
    context.setdefault("site_url", settings.SITE_URL)
    txt = render_to_string(f"emails/{template_base}.txt", context)
    html = render_to_string(f"emails/{template_base}.html", context)
    msg = EmailMultiAlternatives(subject, txt, settings.DEFAULT_FROM_EMAIL, [to])
    msg.attach_alternative(html, "text/html")
    msg.send()


def send_reviewer_invitation(
    email: str, reviewer_name: str, journal_name: str, activation_url: str
) -> None:
    send_template_email(
        to=email,
        subject=f"Invitation à rejoindre l'équipe de relecture — {journal_name}",
        template_base="invitation",
        context={
            "journal_name": journal_name,
            "reviewer_name": reviewer_name,
            "email": email,
            "activation_url": activation_url,
        },
    )
