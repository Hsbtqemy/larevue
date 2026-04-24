from django.db import models
from django_fsm import FSMField, transition

from apps.core.models import BaseModel


class Issue(BaseModel):
    class State(models.TextChoices):
        UNDER_REVIEW = "under_review", "En évaluation"
        ACCEPTED = "accepted", "Accepté"
        IN_REVIEW = "in_review", "En attente des relectures"
        IN_REVISION = "in_revision", "En attente des V2"
        FINAL_CHECK = "final_check", "Vérification finale"
        SENT_TO_PUBLISHER = "sent_to_publisher", "Envoyé à l'éditeur"
        PUBLISHED = "published", "Publié"
        REFUSED = "refused", "Refusé"

    ACTIVE_STATES = [
        State.UNDER_REVIEW,
        State.ACCEPTED,
        State.IN_REVIEW,
        State.IN_REVISION,
        State.FINAL_CHECK,
        State.SENT_TO_PUBLISHER,
    ]

    ARCHIVED_STATES = frozenset({State.PUBLISHED, State.REFUSED})

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
    deadline_articles = models.DateField(
        null=True, blank=True,
        verbose_name="Date limite articles",
        help_text="Date à laquelle tous les articles doivent être reçus.",
    )
    deadline_reviews = models.DateField(
        null=True, blank=True,
        verbose_name="Date limite relectures",
        help_text="Date à laquelle toutes les relectures doivent être reçues.",
    )
    deadline_v2 = models.DateField(
        null=True, blank=True,
        verbose_name="Date limite V2",
        help_text="Date à laquelle les versions révisées doivent être reçues.",
    )
    deadline_final_check = models.DateField(
        null=True, blank=True,
        verbose_name="Date limite vérification finale",
        help_text="Date limite pour la vérification finale avant envoi.",
    )
    deadline_sent_to_publisher = models.DateField(
        null=True, blank=True,
        verbose_name="Date limite envoi à l'éditeur",
        help_text="Date prévue d'envoi à l'éditeur.",
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

    @transition(field=state, source=State.ACCEPTED, target=State.IN_REVIEW)
    def send_to_reviewers(self):
        pass

    @transition(field=state, source=State.IN_REVIEW, target=State.IN_REVISION)
    def reviews_received_return_to_authors(self):
        pass

    @transition(field=state, source=State.IN_REVISION, target=State.FINAL_CHECK)
    def v2_received_final_check(self):
        pass

    @transition(field=state, source=State.FINAL_CHECK, target=State.SENT_TO_PUBLISHER)
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

    @transition(field=state, source=State.IN_REVIEW, target=State.ACCEPTED)
    def recall_reviewers(self):
        pass

    @transition(field=state, source=State.IN_REVISION, target=State.IN_REVIEW)
    def recall_to_authors(self):
        pass

    @transition(field=state, source=State.FINAL_CHECK, target=State.IN_REVISION)
    def reopen_revision(self):
        pass

    @transition(field=state, source=State.SENT_TO_PUBLISHER, target=State.FINAL_CHECK)
    def recall_final_check(self):
        pass

    @transition(field=state, source=State.PUBLISHED, target=State.SENT_TO_PUBLISHER)
    def unpublish(self):
        pass
