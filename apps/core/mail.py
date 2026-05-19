import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


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


def _reviewer_dashboard_url() -> str:
    return settings.SITE_URL + reverse("accounts:reviewer_dashboard")


def _article_url(review) -> str:
    article = review.article
    issue = article.issue
    return settings.SITE_URL + reverse(
        "articles:detail",
        kwargs={"slug": issue.journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def send_review_assigned(review) -> None:
    reviewer = review.reviewer
    if not reviewer or not reviewer.email:
        return
    journal = review.article.issue.journal
    try:
        send_template_email(
            to=reviewer.email,
            subject=f"Nouvelle relecture à effectuer — {journal.name}",
            template_base="review_assigned",
            context={
                "reviewer_name": review.reviewer_name_snapshot,
                "journal_name": journal.name,
                "article_title": review.article.title,
                "deadline": review.deadline.strftime("%d/%m/%Y"),
                "dashboard_url": _reviewer_dashboard_url(),
            },
        )
    except Exception:
        logger.exception("send_review_assigned failed for review %s", review.pk)


def send_review_received_reviewer(review) -> None:
    reviewer = review.reviewer
    if not reviewer or not reviewer.email:
        return
    journal = review.article.issue.journal
    try:
        send_template_email(
            to=reviewer.email,
            subject=f"Relecture bien reçue — {journal.name}",
            template_base="review_received_reviewer",
            context={
                "reviewer_name": review.reviewer_name_snapshot,
                "journal_name": journal.name,
                "article_title": review.article.title,
            },
        )
    except Exception:
        logger.exception("send_review_received_reviewer failed for review %s", review.pk)


def send_review_reminder(review) -> None:
    reviewer = review.reviewer
    if not reviewer or not reviewer.email:
        return
    journal = review.article.issue.journal
    deadline = review.deadline.strftime("%d/%m/%Y")
    try:
        send_template_email(
            to=reviewer.email,
            subject=f"Rappel : relecture à déposer avant le {deadline} — {journal.name}",
            template_base="review_reminder",
            context={
                "reviewer_name": review.reviewer_name_snapshot,
                "journal_name": journal.name,
                "article_title": review.article.title,
                "deadline": deadline,
                "dashboard_url": _reviewer_dashboard_url(),
            },
        )
    except Exception:
        logger.exception("send_review_reminder failed for review %s", review.pk)


def send_review_received_editors(review) -> None:
    from apps.journals.models import Membership

    journal = review.article.issue.journal
    review_url = _article_url(review)
    members = Membership.objects.filter(journal=journal).select_related("user")
    for membership in members:
        user = membership.user
        if not user.email:
            continue
        try:
            send_template_email(
                to=user.email,
                subject=f"Relecture déposée — {review.article.title}",
                template_base="review_received_editors",
                context={
                    "recipient_name": user.get_full_name() or user.email,
                    "article_title": review.article.title,
                    "reviewer_name": review.reviewer_name_snapshot,
                    "review_url": review_url,
                },
            )
        except Exception:
            logger.exception("send_review_received_editors failed for user %s review %s", user.pk, review.pk)
