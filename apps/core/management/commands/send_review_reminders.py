from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.mail import send_review_reminder
from apps.reviews.models import ReviewRequest


class Command(BaseCommand):
    help = "Envoie des rappels aux relecteurs dont la deadline approche"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=3,
            help="Envoie un rappel si la deadline est dans N jours ou moins (défaut : 3)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les rappels qui seraient envoyés sans les envoyer",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now().date() + timedelta(days=days)

        reviews = ReviewRequest.objects.filter(
            state=ReviewRequest.State.SENT,
            deadline__lte=cutoff,
            reminder_sent_at__isnull=True,
        ).select_related(
            "article", "article__issue", "article__issue__journal", "reviewer",
        )

        count = 0
        for review in reviews:
            if not review.reviewer or not review.reviewer.email:
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
            count += 1

        label = "rappel(s) qui seraient envoyés" if dry_run else "rappel(s) envoyé(s)"
        self.stdout.write(self.style.SUCCESS(f"{count} {label}."))
