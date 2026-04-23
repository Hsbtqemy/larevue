from django.db import models
from django_fsm import FSMField, transition

from apps.core.models import BaseModel


class Issue(BaseModel):
    class State(models.TextChoices):
        UNDER_REVIEW = "under_review", "En évaluation"
        ACCEPTED = "accepted", "Accepté"
        IN_PRODUCTION = "in_production", "En production"
        SENT_TO_PUBLISHER = "sent_to_publisher", "Envoyé à l'éditeur"
        PUBLISHED = "published", "Publié"
        REFUSED = "refused", "Refusé"

    ACTIVE_STATES = [
        State.UNDER_REVIEW,
        State.ACCEPTED,
        State.IN_PRODUCTION,
        State.SENT_TO_PUBLISHER,
    ]

    journal = models.ForeignKey(
        "journals.Journal",
        on_delete=models.CASCADE,
        related_name="issues",
        verbose_name="Revue",
    )
    number = models.CharField(
        max_length=20,
        verbose_name="Numéro",
        help_text="Ex : « 14 » ou « 14-15 » pour un double numéro.",
    )
    thematic_title = models.CharField(max_length=300, verbose_name="Titre thématique")
    description = models.TextField(blank=True, verbose_name="Description")
    editor_name = models.CharField(
        max_length=200,
        verbose_name="Responsable éditorial·e",
        help_text="Champ texte libre — souvent une personne extérieure au comité.",
    )
    planned_publication_date = models.DateField(
        blank=True, null=True, verbose_name="Date de parution prévue"
    )
    cover_image = models.ImageField(
        upload_to="issues/covers/", blank=True, null=True, verbose_name="Image de couverture"
    )
    final_pdf = models.FileField(
        upload_to="issues/final_pdfs/", blank=True, null=True, verbose_name="PDF final"
    )
    state = FSMField(
        default=State.UNDER_REVIEW,
        choices=State.choices,
        protected=True,
        verbose_name="État",
    )

    class Meta:
        verbose_name = "Numéro"
        verbose_name_plural = "Numéros"
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["journal", "number"], name="unique_issue_number")
        ]

    def __str__(self):
        return f"N°{self.number} — {self.thematic_title}"

    def get_badge_tone(self) -> str:
        from apps.core.display import ISSUE_TONES
        return ISSUE_TONES.get(self.state, "neutral")

    @property
    def progress(self) -> int:
        """Pourcentage d'articles validés sur le total. Retourne 0 si aucun article."""
        total = self.articles.count()
        if total == 0:
            return 0
        validated = self.articles.filter(state="validated").count()
        return int((validated / total) * 100)

    # ------------------------------------------------------------------ #
    # Transitions FSM — flux normal                                        #
    # ------------------------------------------------------------------ #

    @transition(field=state, source=State.UNDER_REVIEW, target=State.ACCEPTED)
    def accept(self):
        pass

    @transition(field=state, source=State.UNDER_REVIEW, target=State.REFUSED)
    def refuse(self):
        pass

    @transition(field=state, source=State.ACCEPTED, target=State.IN_PRODUCTION)
    def start_production(self):
        pass

    @transition(field=state, source=State.IN_PRODUCTION, target=State.SENT_TO_PUBLISHER)
    def send_to_publisher(self):
        pass

    @transition(field=state, source=State.SENT_TO_PUBLISHER, target=State.PUBLISHED)
    def mark_as_published(self):
        pass

    # ------------------------------------------------------------------ #
    # Transitions FSM — rollbacks                                          #
    # ------------------------------------------------------------------ #

    @transition(field=state, source=State.ACCEPTED, target=State.UNDER_REVIEW)
    def reopen_for_review(self):
        pass

    @transition(field=state, source=State.IN_PRODUCTION, target=State.ACCEPTED)
    def pause_production(self):
        pass

    @transition(field=state, source=State.SENT_TO_PUBLISHER, target=State.IN_PRODUCTION)
    def recall_from_publisher(self):
        pass

    # Protégé par une confirmation UI — état terminal quasi-sûr mais rattrapable.
    @transition(field=state, source=State.PUBLISHED, target=State.SENT_TO_PUBLISHER)
    def unpublish(self):
        pass
