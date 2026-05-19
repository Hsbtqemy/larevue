from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.mail import send_review_reminder
from apps.reviews.models import ReviewRequest


class Command(BaseCommand):
    help = "Envoie les rappels automatiques aux relecteurs dont la deadline approche."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les rappels qui seraient envoyés sans les envoyer.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        sent = 0

        candidates = (
            ReviewRequest.objects.filter(
                state=ReviewRequest.State.SENT,
                reminder_sent_at__isnull=True,
                article__issue__journal__auto_reminder_days__isnull=False,
            )
            .select_related("reviewer__user", "article__issue__journal")
        )

        for review in candidates:
            journal = review.article.issue.journal
            target_date = review.deadline - timedelta(days=journal.auto_reminder_days)
            if target_date != today:
                continue
            if dry_run:
                self.stdout.write(
                    f"[dry-run] Rappel → {review.reviewer.email} "
                    f"(deadline : {review.deadline:%d/%m/%Y}, article : {review.article.title})"
                )
            else:
                send_review_reminder(review)
                review.reminder_sent_at = timezone.now()
                review.save(update_fields=["reminder_sent_at"])
                self.stdout.write(f"  Rappel envoyé : {review}")
            sent += 1

        label = "qui seraient envoyés" if dry_run else "envoyé(s)"
        self.stdout.write(self.style.SUCCESS(f"{sent} rappel(s) {label}."))
