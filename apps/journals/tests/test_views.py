import pytest
from django.urls import reverse

from apps.journals.models import Journal, Membership


# ------------------------------------------------------------------ #
# HomeView                                                            #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestHomeView:
    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_zero_journals_shows_empty_message(self, client, user):
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code == 200
        assert "aucune revue" in response.content.decode().lower()

    def test_one_journal_redirects_to_dashboard(self, client, user, membership):
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert response["Location"] == reverse(
            "journal_dashboard", kwargs={"slug": membership.journal.slug}
        )

    def test_multiple_journals_shows_list(self, client, user, membership, db):
        second_journal = Journal.objects.create(name="Deuxième revue", slug="deuxieme-revue")
        Membership.objects.create(user=user, journal=second_journal)
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert membership.journal.name in content
        assert second_journal.name in content


# ------------------------------------------------------------------ #
# JournalDashboardView                                                #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestJournalDashboardView:
    def test_unauthenticated_redirects_to_login(self, client, journal):
        response = client.get(reverse("journal_dashboard", kwargs={"slug": journal.slug}))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_member_can_access(self, client, user, membership):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert response.status_code == 200
        assert membership.journal.name in response.content.decode()

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User

        other_user = User.objects.create_user(email="other@example.com", password="pass")
        other_journal = Journal.objects.create(name="Autre revue", slug="autre-revue")
        Membership.objects.create(user=other_user, journal=other_journal)

        intruder = User.objects.create_user(email="intrus@example.com", password="pass")
        client.force_login(intruder)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": other_journal.slug})
        )
        assert response.status_code == 403

    def test_nonexistent_slug_returns_404(self, client, user):
        client.force_login(user)
        response = client.get(reverse("journal_dashboard", kwargs={"slug": "nexiste-pas"}))
        assert response.status_code == 404

    def test_active_issues_shown(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert issue.thematic_title in response.content.decode()

    def test_published_issue_not_shown(self, client, user, membership, issue):
        # Bypass FSM protection for test setup
        from apps.issues.models import Issue as IssueModel

        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.PUBLISHED)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert issue.thematic_title not in response.content.decode()

    def test_back_link_visible_with_multiple_journals(self, client, user, membership, db):
        second_journal = Journal.objects.create(name="Troisième revue", slug="troisieme-revue")
        Membership.objects.create(user=user, journal=second_journal)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert "Mes revues" in response.content.decode()

    def test_back_link_hidden_with_single_journal(self, client, user, membership):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert "Mes revues" not in response.content.decode()
