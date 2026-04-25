import json

import pytest
from django.urls import reverse

from apps.accounts.models import User

PROFILE_URL = reverse("accounts:profile")
PATCH_URL = reverse("accounts:profile_patch")


def _patch(client, field, value):
    return client.post(
        PATCH_URL,
        data=json.dumps({"field": field, "value": value}),
        content_type="application/json",
    )


@pytest.mark.django_db
class TestProfileView:
    def test_unauthenticated_redirects(self, client):
        res = client.get(PROFILE_URL)
        assert res.status_code == 302
        assert "/accounts/" in res["Location"]

    def test_authenticated_returns_200(self, client, user):
        client.force_login(user)
        res = client.get(PROFILE_URL)
        assert res.status_code == 200

    def test_shows_user_name(self, client, user):
        client.force_login(user)
        res = client.get(PROFILE_URL)
        assert user.first_name in res.content.decode()
        assert user.last_name in res.content.decode()

    def test_shows_user_email(self, client, user):
        client.force_login(user)
        res = client.get(PROFILE_URL)
        assert user.email in res.content.decode()


@pytest.mark.django_db
class TestProfilePatchView:
    def test_unauthenticated_redirects(self, client):
        res = _patch(client, "first_name", "Alice")
        assert res.status_code == 302

    def test_patch_first_name(self, client, user):
        client.force_login(user)
        res = _patch(client, "first_name", "Alice")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "Alice"

    def test_patch_last_name(self, client, user):
        client.force_login(user)
        res = _patch(client, "last_name", "Martin")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.last_name == "Martin"

    def test_empty_first_name_returns_error(self, client, user):
        client.force_login(user)
        original = user.first_name
        res = _patch(client, "first_name", "")
        assert res.status_code == 400
        user.refresh_from_db()
        assert user.first_name == original

    def test_empty_last_name_returns_error(self, client, user):
        client.force_login(user)
        original = user.last_name
        res = _patch(client, "last_name", "")
        assert res.status_code == 400
        user.refresh_from_db()
        assert user.last_name == original

    def test_disallowed_field_returns_error(self, client, user):
        client.force_login(user)
        res = _patch(client, "is_staff", "true")
        assert res.status_code == 400
        user.refresh_from_db()
        assert not user.is_staff

    def test_invalid_json_returns_error(self, client, user):
        client.force_login(user)
        res = client.post(PATCH_URL, data="not-json", content_type="application/json")
        assert res.status_code == 400

    def test_each_user_patches_only_themselves(self, client, user):
        other = User.objects.create_user(
            email="other@test.com", password="pass",
            first_name="Other", last_name="User",
        )
        client.force_login(other)
        res = _patch(client, "first_name", "Hacked")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.first_name != "Hacked"
        other.refresh_from_db()
        assert other.first_name == "Hacked"

    def test_patch_email(self, client, user):
        client.force_login(user)
        res = _patch(client, "email", "nouveau@example.com")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.email == "nouveau@example.com"

    def test_duplicate_email_returns_error(self, client, user):
        other = User.objects.create_user(
            email="taken@example.com", password="pass",
            first_name="X", last_name="Y",
        )
        client.force_login(user)
        original = user.email
        res = _patch(client, "email", other.email)
        assert res.status_code == 400
        user.refresh_from_db()
        assert user.email == original

    def test_empty_email_returns_error(self, client, user):
        client.force_login(user)
        original = user.email
        res = _patch(client, "email", "")
        assert res.status_code == 400
        user.refresh_from_db()
        assert user.email == original

    def test_invalid_email_returns_error(self, client, user):
        client.force_login(user)
        original = user.email
        res = _patch(client, "email", "not-an-email")
        assert res.status_code == 400
        user.refresh_from_db()
        assert user.email == original
