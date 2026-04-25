from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel, TimestampedModel


class Journal(BaseModel):
    ACCENT_CHOICES = [
        ("terracotta", "Terracotta"),
        ("olive", "Olive"),
        ("slate", "Ardoise"),
        ("plum", "Prune"),
        ("ochre", "Ocre"),
    ]

    name = models.CharField(max_length=200, unique=True, verbose_name="Nom")
    slug = models.SlugField(unique=True, verbose_name="Identifiant URL")
    description = models.TextField(blank=True, verbose_name="Description")
    logo = models.ImageField(
        upload_to="journals/logos/", blank=True, null=True, verbose_name="Logo"
    )
    accent_color = models.CharField(
        max_length=20,
        choices=ACCENT_CHOICES,
        default="terracotta",
        verbose_name="Couleur d'accentuation",
    )

    directors = models.CharField(
        max_length=500, blank=True, verbose_name="Direction de la revue",
        help_text="Noms des directeurs/directrices, séparés par des virgules.",
    )
    publisher = models.CharField(max_length=200, blank=True, verbose_name="Éditeur")
    issn_print = models.CharField(
        max_length=9, blank=True, verbose_name="ISSN papier",
        help_text="Format : XXXX-XXXX",
    )
    issn_online = models.CharField(
        max_length=9, blank=True, verbose_name="ISSN en ligne",
        help_text="Format : XXXX-XXXX",
    )
    periodicity = models.CharField(max_length=100, blank=True, verbose_name="Périodicité")
    founded_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Année de fondation",
    )
    website = models.URLField(max_length=300, blank=True, verbose_name="Site web")

    class Meta:
        verbose_name = "Revue"
        verbose_name_plural = "Revues"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Membership(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Utilisateur·ice",
    )
    journal = models.ForeignKey(
        Journal,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Revue",
    )

    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        constraints = [
            models.UniqueConstraint(fields=["user", "journal"], name="unique_membership")
        ]

    def __str__(self):
        return f"{self.user} — {self.journal}"
