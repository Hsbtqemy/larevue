from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel, TimestampedModel


class Journal(BaseModel):
    name = models.CharField(max_length=200, unique=True, verbose_name="Nom")
    slug = models.SlugField(unique=True, verbose_name="Identifiant URL")
    description = models.TextField(blank=True, verbose_name="Description")
    logo = models.ImageField(
        upload_to="journals/logos/", blank=True, null=True, verbose_name="Logo"
    )
    accent_color = models.CharField(
        max_length=7,
        default="#000000",
        verbose_name="Couleur d'accentuation",
        help_text="Code hexadécimal (ex : #3B82F6) pour personnaliser l'interface.",
    )

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
