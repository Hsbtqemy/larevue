from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.core.storage import VersionedUploadTo


class ReviewRequest(BaseModel):
    class State(models.TextChoices):
        ASSIGNED = "assigned", "Désignée"
        SENT = "sent", "Envoyée"
        RECEIVED = "received", "Reçue"
        DECLINED = "declined", "Refusée"

    class Verdict(models.TextChoices):
        FAVORABLE = "favorable", "Favorable"
        NEEDS_REVISION = "needs_revision", "Révision requise"
        UNFAVORABLE = "unfavorable", "Défavorable"

    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.CASCADE,
        related_name="review_requests",
        verbose_name="Article",
    )
    article_version = models.ForeignKey(
        "articles.ArticleVersion",
        on_delete=models.PROTECT,
        verbose_name="Version relue",
    )
    reviewer = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relecteur·ice",
    )
    reviewer_name_snapshot = models.CharField(
        max_length=200, verbose_name="Nom du relecteur·ice (snapshot)"
    )
    deadline = models.DateField(verbose_name="Date limite")
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ASSIGNED,
        verbose_name="État",
    )
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Envoyée le")
    received_file = models.FileField(
        upload_to=VersionedUploadTo("reviews/files"),
        blank=True,
        null=True,
        verbose_name="Fichier de relecture",
    )
    received_at = models.DateTimeField(blank=True, null=True, verbose_name="Reçue le")
    verdict = models.CharField(
        max_length=20,
        choices=Verdict.choices,
        blank=True,
        verbose_name="Verdict",
    )
    internal_notes = models.TextField(blank=True, verbose_name="Notes internes")

    class Meta:
        verbose_name = "Demande de relecture"
        verbose_name_plural = "Demandes de relecture"
        ordering = ["deadline"]

    def __str__(self):
        return f"Relecture de « {self.article} » par {self.reviewer_name_snapshot}"

    @property
    def is_overdue(self) -> bool:
        return self.state == self.State.SENT and self.deadline < timezone.now().date()
