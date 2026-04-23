from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """Manager par défaut : exclut les enregistrements soft-deletés."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Manager alternatif incluant les enregistrements soft-deletés."""

    pass


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Supprimé le")

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        # Soft delete par défaut : préserve l'historique (relectures, versions, etc.)
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Suppression physique irréversible."""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class BaseModel(TimestampedModel, SoftDeleteModel):
    """Modèle de base pour toutes les entités métier : timestamps + soft delete."""

    class Meta:
        abstract = True
