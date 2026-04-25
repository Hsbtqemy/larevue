import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.text import slugify

from apps.core.models import BaseModel, TimestampedModel


def _journal_doc_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"journal_documents/{instance.journal_id}/{uuid.uuid4().hex}{ext}"


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


class JournalDocument(models.Model):
    journal = models.ForeignKey(
        Journal,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    name = models.CharField(max_length=200, verbose_name="Nom du document")
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Optionnel — pour préciser le contenu du document.",
    )
    file = models.FileField(
        upload_to=_journal_doc_upload_to,
        verbose_name="Fichier",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Ajouté par",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Document de la revue"
        verbose_name_plural = "Documents de la revue"

    def __str__(self):
        return self.name


@receiver(post_delete, sender=JournalDocument)
def _delete_journal_document_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


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
