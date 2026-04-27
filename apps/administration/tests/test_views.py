import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.journals.models import Journal, Membership


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="admin@example.com",
        first_name="Super",
        last_name="Admin",
        password="adminpass123",
    )


# ------------------------------------------------------------------ #
# Access control                                                      #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestSuperuserRequired:
    def test_anonymous_redirects_to_login(self, client):
        response = client.get(reverse("administration:index"))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_regular_user_gets_403(self, client, user):
        client.force_login(user)
        response = client.get(reverse("administration:index"))
        assert response.status_code == 403

    def test_superuser_gets_200(self, client, superuser):
        client.force_login(superuser)
        response = client.get(reverse("administration:index"))
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# AdministrationView                                                  #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestAdministrationView:
    def test_shows_journals_and_users(self, client, superuser, journal, user):
        client.force_login(superuser)
        response = client.get(reverse("administration:index"))
        content = response.content.decode()
        assert journal.name in content
        assert user.get_full_name() in content

    def test_empty_state(self, client, superuser):
        client.force_login(superuser)
        response = client.get(reverse("administration:index"))
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# JournalCreateView                                                   #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestJournalCreateView:
    def test_creates_journal_and_adds_superuser_as_member(self, client, superuser):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_create"),
            {"name": "Nouvelle revue", "slug": "nouvelle-revue", "accent_color": "terracotta"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "redirect_url" in data
        journal = Journal.objects.get(slug="nouvelle-revue")
        assert Membership.objects.filter(user=superuser, journal=journal).exists()

    def test_duplicate_slug_returns_errors(self, client, superuser, journal):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_create"),
            {"name": "Autre revue", "slug": journal.slug, "accent_color": "olive"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "slug" in data["errors"]

    def test_non_superuser_gets_403(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse("administration:journal_create"),
            {"name": "X", "slug": "x", "accent_color": "terracotta"},
        )
        assert response.status_code == 403


# ------------------------------------------------------------------ #
# UserCreateView                                                      #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestUserCreateView:
    def test_creates_user_with_temp_password_flag(self, client, superuser):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:user_create"),
            {"email": "new@example.com", "first_name": "Alice", "last_name": "Dupont"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "redirect_url" in data
        user = User.objects.get(email="new@example.com")
        assert user.must_change_password is True

    def test_temp_password_in_session(self, client, superuser):
        client.force_login(superuser)
        client.post(
            reverse("administration:user_create"),
            {"email": "new2@example.com", "first_name": "Bob", "last_name": "Martin"},
        )
        assert "temp_password" in client.session

    def test_duplicate_email_returns_error(self, client, superuser, user):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:user_create"),
            {"email": user.email, "first_name": "X", "last_name": "Y"},
        )
        assert response.status_code == 400
        assert "email" in response.json()["errors"]


# ------------------------------------------------------------------ #
# UserPasswordDisplayView                                             #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestUserPasswordDisplayView:
    def test_shows_password_from_session(self, client, superuser, user):
        client.force_login(superuser)
        session = client.session
        session["temp_password"] = "s3cretPa$$"
        session["temp_password_user_id"] = user.pk
        session.save()
        response = client.get(
            reverse("administration:user_password_display", kwargs={"user_id": user.pk})
        )
        assert response.status_code == 200
        assert "s3cretPa$$" in response.content.decode()

    def test_password_consumed_after_display(self, client, superuser, user):
        client.force_login(superuser)
        session = client.session
        session["temp_password"] = "s3cretPa$$"
        session["temp_password_user_id"] = user.pk
        session.save()
        client.get(reverse("administration:user_password_display", kwargs={"user_id": user.pk}))
        assert "temp_password" not in client.session

    def test_without_session_redirects(self, client, superuser, user):
        client.force_login(superuser)
        response = client.get(
            reverse("administration:user_password_display", kwargs={"user_id": user.pk})
        )
        assert response.status_code == 302
        assert response["Location"] == reverse("administration:index")


# ------------------------------------------------------------------ #
# UserResetPasswordView                                               #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestUserResetPasswordView:
    def test_reset_sets_must_change_flag(self, client, superuser, user):
        user.must_change_password = False
        user.save()
        client.force_login(superuser)
        response = client.post(
            reverse("administration:user_reset_password", kwargs={"user_id": user.pk})
        )
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.must_change_password is True

    def test_reset_stores_password_in_session(self, client, superuser, user):
        client.force_login(superuser)
        client.post(
            reverse("administration:user_reset_password", kwargs={"user_id": user.pk})
        )
        assert "temp_password" in client.session


# ------------------------------------------------------------------ #
# MustChangePasswordMiddleware                                        #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestMustChangePasswordMiddleware:
    def test_redirects_user_with_flag(self, client, user):
        user.must_change_password = True
        user.save()
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:profile_password")

    def test_no_redirect_for_normal_user(self, client, user, membership):
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code in (200, 302)
        if response.status_code == 302:
            assert "profile_password" not in response["Location"]

    def test_no_redirect_on_password_change_url(self, client, user):
        user.must_change_password = True
        user.save()
        client.force_login(user)
        response = client.get(reverse("accounts:profile_password"), follow=False)
        assert response.status_code in (200, 302, 405)
        if response.status_code == 302:
            assert "profile_password" not in response["Location"]

    def test_flag_cleared_after_password_change(self, client, user):
        user.must_change_password = True
        user.save()
        client.force_login(user)
        response = client.post(
            reverse("accounts:profile_password"),
            {"current_password": "testpass123", "new_password": "NewPass!987", "new_password_confirm": "NewPass!987"},
        )
        user.refresh_from_db()
        assert user.must_change_password is False


# ------------------------------------------------------------------ #
# JournalMembersView                                                  #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestJournalMembersView:
    def test_shows_member_list(self, client, superuser, journal, membership):
        client.force_login(superuser)
        response = client.get(
            reverse("administration:journal_members", kwargs={"slug": journal.slug})
        )
        assert response.status_code == 200
        assert membership.user.get_full_name() in response.content.decode()

    def test_add_member(self, client, superuser, journal, user):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_member_add", kwargs={"slug": journal.slug}),
            {"user_id": user.pk},
        )
        assert response.status_code == 200
        assert Membership.objects.filter(user=user, journal=journal).exists()

    def test_add_existing_member_returns_error(self, client, superuser, journal, membership):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_member_add", kwargs={"slug": journal.slug}),
            {"user_id": membership.user.pk},
        )
        assert response.status_code == 400

    def test_remove_member(self, client, superuser, journal, membership):
        client.force_login(superuser)
        response = client.delete(
            reverse(
                "administration:journal_member_remove",
                kwargs={"slug": journal.slug, "user_id": membership.user.pk},
            )
        )
        assert response.status_code == 200
        assert not Membership.objects.filter(user=membership.user, journal=journal).exists()


# ------------------------------------------------------------------ #
# JournalMemberQuickCreateView                                        #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestJournalMemberQuickCreateView:
    def test_creates_user_and_adds_to_journal(self, client, superuser, journal):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_member_quick_create", kwargs={"slug": journal.slug}),
            {"email": "quick@example.com", "first_name": "Quick", "last_name": "User"},
        )
        assert response.status_code == 200
        user = User.objects.get(email="quick@example.com")
        assert user.must_change_password is True
        assert Membership.objects.filter(user=user, journal=journal).exists()

    def test_duplicate_email_returns_error(self, client, superuser, journal, user):
        client.force_login(superuser)
        response = client.post(
            reverse("administration:journal_member_quick_create", kwargs={"slug": journal.slug}),
            {"email": user.email, "first_name": "X", "last_name": "Y"},
        )
        assert response.status_code == 400
        assert "email" in response.json()["errors"]
