from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    # On supprime le champ username hérité : l'e-mail est l'identifiant unique.
    username = None
    email = models.EmailField(unique=True, verbose_name="Adresse e-mail")
    first_name = models.CharField(max_length=150, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, verbose_name="Nom")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    must_change_password = models.BooleanField(
        default=False,
        verbose_name="Doit changer son mot de passe",
        help_text="Forcé à la première connexion après création ou reset par un superuser.",
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Utilisateur·ice"
        verbose_name_plural = "Utilisateur·ices"

    def __str__(self):
        full = self.get_full_name()
        return f"{full} <{self.email}>" if full else self.email
