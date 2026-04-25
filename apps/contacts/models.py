from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import BaseModel


class Contact(BaseModel):
    class Role(models.TextChoices):
        AUTHOR = "author", "Auteur·ice"
        INTERNAL_REVIEWER = "internal_reviewer", "Relecteur·ice interne"
        EXTERNAL_REVIEWER = "external_reviewer", "Relecteur·ice externe"

    journal = models.ForeignKey(
        "journals.Journal",
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Revue",
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    email = models.EmailField(blank=True, verbose_name="Adresse e-mail")
    affiliation = models.CharField(max_length=200, blank=True, verbose_name="Affiliation")
    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
        help_text="Spécialités, compétences, contexte de collaboration…",
    )
    # ArrayField PostgreSQL : simple et suffisant pour un nombre fixe de rôles connus.
    usual_roles = ArrayField(
        models.CharField(max_length=50, choices=Role.choices),
        default=list,
        blank=True,
        verbose_name="Rôles habituels",
    )

    class Meta:
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def usual_roles_display(self) -> list[str]:
        role_map = dict(self.Role.choices)
        return [role_map.get(r, r) for r in self.usual_roles]
