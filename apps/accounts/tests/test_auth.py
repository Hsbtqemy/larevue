import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
class TestLogin:
    def test_valid_login_redirects(self, client, user, membership):
        # Login → redirige vers home, home → redirige vers dashboard (1 seule revue)
        response = client.post(
            reverse("account_login"),
            {"login": user.email, "password": "testpass123"},
            follow=True,
        )
        assert response.status_code == 200
        assert membership.journal.name in response.content.decode()

    def test_invalid_password_returns_form(self, client, user):
        response = client.post(
            reverse("account_login"),
            {"login": user.email, "password": "mauvais-mdp"},
        )
        assert response.status_code == 200

    def test_signup_does_not_create_user(self, client):
        # L'adapter bloque l'inscription — un POST ne crée aucun utilisateur.
        before = User.objects.count()
        client.post(
            reverse("account_signup"),
            {
                "email": "nouveau@example.com",
                "password1": "motdepasse123!",
                "password2": "motdepasse123!",
            },
        )
        assert User.objects.count() == before
