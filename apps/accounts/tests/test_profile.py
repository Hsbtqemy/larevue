import json

import pytest
from django.urls import reverse

from apps.accounts.models import User

PROFILE_URL = reverse("accounts:profile")
PATCH_URL = reverse("accounts:profile_patch")
PASSWORD_URL = reverse("accounts:profile_password")


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

    def test_shows_only_own_journals(self, client, user, membership, journal):
        from apps.journals.models import Journal
        other = Journal.objects.create(name="Autre revue", slug="autre-revue-profile")
        client.force_login(user)
        res = client.get(PROFILE_URL)
        content = res.content.decode()
        assert journal.name in content
        assert other.name not in content

    def test_journal_counters_present(self, client, user, membership, journal):
        client.force_login(user)
        res = client.get(PROFILE_URL)
        content = res.content.decode()
        assert "0 numéro" in content
        assert "1 membre" in content


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


def _change_password(client, current, new, confirm):
    return client.post(PASSWORD_URL, {
        "current_password": current,
        "new_password": new,
        "new_password_confirm": confirm,
    })


@pytest.mark.django_db
class TestProfilePasswordView:
    def test_unauthenticated_redirects(self, client):
        res = _change_password(client, "testpass123", "newpass456", "newpass456")
        assert res.status_code == 302
        assert "/accounts/" in res["Location"]

    def test_valid_change_redirects_with_success(self, client, user):
        client.force_login(user)
        res = _change_password(client, "testpass123", "newpass456", "newpass456")
        assert res.status_code == 302
        assert "pw=ok" in res["Location"]

    def test_valid_change_updates_password(self, client, user):
        client.force_login(user)
        _change_password(client, "testpass123", "newpass456", "newpass456")
        user.refresh_from_db()
        assert user.check_password("newpass456")

    def test_valid_change_preserves_session(self, client, user):
        client.force_login(user)
        _change_password(client, "testpass123", "newpass456", "newpass456")
        res = client.get(PROFILE_URL)
        assert res.status_code == 200

    def test_wrong_current_password_rerenders(self, client, user):
        client.force_login(user)
        res = _change_password(client, "wrong-password", "newpass456", "newpass456")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.check_password("testpass123")

    def test_new_password_too_short_rerenders(self, client, user):
        client.force_login(user)
        res = _change_password(client, "testpass123", "short", "short")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.check_password("testpass123")

    def test_confirmation_mismatch_rerenders(self, client, user):
        client.force_login(user)
        res = _change_password(client, "testpass123", "newpass456", "different789")
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.check_password("testpass123")
