from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition

from apps.core.models import BaseModel, TimestampedModel
from apps.core.storage import VersionedUploadTo


class Article(BaseModel):
    class State(models.TextChoices):
        PENDING = "pending", "En attente"
        RECEIVED = "received", "Reçu"
        IN_REVIEW = "in_review", "En relecture"
        REVIEWS_RECEIVED = "reviews_received", "Relectures reçues"
        IN_AUTHOR_REVISION = "in_author_revision", "En révision auteur"
        REVISED = "revised", "Révisé"
        VALIDATED = "validated", "Validé"

    class Type(models.TextChoices):
        ARTICLE = "article", "Article"
        INTRODUCTION = "introduction", "Introduction"
        SUMMARY = "summary", "Résumé"
        REVIEW = "review", "Recension"
        INTERVIEW = "interview", "Entretien"
        OTHER = "other", "Autre"

    issue = models.ForeignKey(
        "issues.Issue",
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name="Numéro",
    )
    title = models.CharField(max_length=500, verbose_name="Titre")
    author = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authored_articles",
        verbose_name="Auteur·ice",
    )
    author_name_override = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom affiché (forçage)",
        help_text="Laissez vide pour utiliser le nom du contact.",
    )
    article_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.ARTICLE,
        verbose_name="Type",
    )
    abstract = models.TextField(blank=True, verbose_name="Résumé")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre dans le numéro")
    state = FSMField(
        default=State.PENDING,
        choices=State.choices,
        protected=True,
        verbose_name="État",
    )

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.title

    def get_badge_tone(self) -> str:
        from apps.core.display import ARTICLE_TONES
        return ARTICLE_TONES.get(self.state, "neutral")

    @property
    def displayed_author_name(self) -> str:
        if self.author_name_override:
            return self.author_name_override
        return self.author.full_name if self.author else ""

    # ------------------------------------------------------------------ #
    # Transitions FSM                                                      #
    # ------------------------------------------------------------------ #

    @transition(field=state, source=State.PENDING, target=State.RECEIVED)
    def mark_received(self):
        pass

    # Source multiple : même méthode pour le 1er et les tours suivants.
    @transition(field=state, source=[State.RECEIVED, State.REVISED], target=State.IN_REVIEW)
    def send_to_review(self):
        pass

    @transition(field=state, source=State.IN_REVIEW, target=State.RECEIVED)
    def cancel_review(self):
        """Annule l'envoi en relecture en cas d'erreur de saisie."""
        pass

    @transition(field=state, source=State.IN_REVIEW, target=State.REVIEWS_RECEIVED)
    def mark_reviews_received(self):
        pass

    @transition(field=state, source=State.REVIEWS_RECEIVED, target=State.IN_AUTHOR_REVISION)
    def send_to_author(self):
        pass

    # Validation directe si toutes les relectures sont favorables sans révision.
    @transition(
        field=state,
        source=[State.REVIEWS_RECEIVED, State.REVISED],
        target=State.VALIDATED,
    )
    def validate(self):
        pass

    @transition(field=state, source=State.IN_AUTHOR_REVISION, target=State.REVISED)
    def mark_as_revised(self):
        pass

    # Nouvelles corrections sans relecture externe (rare mais prévu).
    @transition(field=state, source=State.REVISED, target=State.IN_AUTHOR_REVISION)
    def request_more_revision(self):
        pass


class ArticleVersion(TimestampedModel):
    # Pas de soft delete : les versions sont un historique immuable.
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Article",
    )
    version_number = models.PositiveIntegerField(verbose_name="Numéro de version")
    file = models.FileField(upload_to=VersionedUploadTo("articles/versions"), verbose_name="Fichier")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Déposé par",
    )
    comment = models.TextField(blank=True, verbose_name="Commentaire")

    class Meta:
        verbose_name = "Version d'article"
        verbose_name_plural = "Versions d'article"
        ordering = ["version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "version_number"], name="unique_article_version"
            )
        ]

    def __str__(self):
        return f"{self.article} — v{self.version_number}"

    def save(self, *args, **kwargs):
        if not self.pk:
            # Auto-incrémente en prenant la dernière version existante pour cet article.
            last = (
                ArticleVersion.objects.filter(article=self.article)
                .order_by("-version_number")
                .values_list("version_number", flat=True)
                .first()
            )
            self.version_number = (last or 0) + 1
        super().save(*args, **kwargs)


class InternalNote(TimestampedModel):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="internal_notes",
        verbose_name="Article",
    )
    issue = models.ForeignKey(
        "issues.Issue",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="internal_notes",
        verbose_name="Numéro",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Auteur·ice",
    )
    content = models.TextField(verbose_name="Contenu")
    is_automatic = models.BooleanField(
        default=False,
        verbose_name="Note automatique",
        help_text="Cochée si générée par le système (changement d'état, de titre, etc.).",
    )

    class Meta:
        verbose_name = "Note interne"
        verbose_name_plural = "Notes internes"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(article__isnull=False, issue__isnull=True)
                    | models.Q(article__isnull=True, issue__isnull=False)
                ),
                name="internalnote_article_xor_issue",
            ),
        ]

    def __str__(self):
        prefix = "[auto] " if self.is_automatic else ""
        subject = self.article or self.issue
        return f"{prefix}Note sur « {subject} »"
