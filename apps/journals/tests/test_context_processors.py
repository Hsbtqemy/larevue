import pytest
from django.urls import reverse

from apps.journals.models import Journal, Membership


@pytest.mark.django_db
class TestUserJournalsContextProcessor:
    def test_unauthenticated_gets_empty_list(self, client, journal):
        response = client.get(reverse("journal_dashboard", kwargs={"slug": journal.slug}))
        # Unauthenticated → redirect, context not rendered — test via direct call instead
        from django.test import RequestFactory
        from apps.journals.context_processors import user_journals as cp

        class AnonymousUser:
            is_authenticated = False

        rf = RequestFactory()
        request = rf.get("/")
        request.user = AnonymousUser()
        result = cp(request)
        assert result == {"user_journals": []}

    def test_single_journal_in_context(self, client, user, membership):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert "user_journals" in response.context
        assert len(response.context["user_journals"]) == 1
        assert response.context["user_journals"][0].pk == membership.journal.pk

    def test_multiple_journals_in_context(self, client, user, membership, db):
        second = Journal.objects.create(name="Deuxième", slug="deuxieme")
        Membership.objects.create(user=user, journal=second)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        pks = {j.pk for j in response.context["user_journals"]}
        assert membership.journal.pk in pks
        assert second.pk in pks

    def test_other_users_journals_not_included(self, client, user, membership, db):
        from apps.accounts.models import User as AppUser

        other = AppUser.objects.create_user(email="other@x.com", password="pass")
        other_journal = Journal.objects.create(name="Autre", slug="autre")
        Membership.objects.create(user=other, journal=other_journal)

        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        pks = {j.pk for j in response.context["user_journals"]}
        assert other_journal.pk not in pks


@pytest.mark.django_db
class TestSidebarSwitcher:
    def test_single_journal_no_popover(self, client, user, membership):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        content = response.content.decode()
        assert "revueSwitcher" not in content
        assert "revue-switcher-current" in content

    def test_multiple_journals_shows_popover(self, client, user, membership, db):
        second = Journal.objects.create(name="Deuxième", slug="deuxieme-pop")
        Membership.objects.create(user=user, journal=second)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        content = response.content.decode()
        assert "revueSwitcher" in content
        assert second.name in content

    def test_current_journal_marked_in_popover(self, client, user, membership, db):
        second = Journal.objects.create(name="Autre revue", slug="autre-pop")
        Membership.objects.create(user=user, journal=second)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        content = response.content.decode()
        assert 'class="popover-item on"' in content
