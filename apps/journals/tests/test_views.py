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

    def test_switcher_link_visible_with_multiple_journals(self, client, user, membership, db):
        # New design: sidebar switcher is an <a href="/"> when user has > 1 journal.
        second_journal = Journal.objects.create(name="Troisième revue", slug="troisieme-revue")
        Membership.objects.create(user=user, journal=second_journal)
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert 'href="/"' in response.content.decode()

    def test_switcher_not_a_link_with_single_journal(self, client, user, membership):
        # New design: sidebar switcher is a static <div> (no href) when user has 1 journal.
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        assert 'href="/"' not in response.content.decode()

    def test_issue_cards_link_to_detail_no_delete_trigger(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        content = response.content.decode()
        expected_url = reverse(
            "issues:detail",
            kwargs={"slug": membership.journal.slug, "issue_id": issue.pk},
        )
        assert f'href="{expected_url}"' in content
        assert "confirmDelete" not in content
        assert "openModal()" not in content


# ------------------------------------------------------------------ #
# JournalDashboardView — contexte enrichi                             #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestDashboardContext:
    def test_context_has_expected_keys(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        ctx = response.context
        assert "active_issues" in ctx
        assert "late_reviews" in ctx
        assert "late_issues" in ctx
        assert "late_count" in ctx
        assert "upcoming_deadlines" in ctx

    def test_article_count_annotation(self, client, user, membership, issue, article):
        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        issues = response.context["active_issues"]
        assert len(issues) == 1
        assert issues[0].article_count == 1
        assert issues[0].validated_count == 0
        assert issues[0].pct == 0

    def test_late_review_appears_in_watch_list(self, client, user, membership, issue, article):
        import datetime

        from apps.articles.models import ArticleVersion
        from apps.reviews.models import ReviewRequest

        version = ArticleVersion.objects.create(
            article=article,
            file="test.pdf",
            uploaded_by=user,
        )
        past_date = datetime.date.today() - datetime.timedelta(days=5)
        ReviewRequest.objects.create(
            article=article,
            article_version=version,
            reviewer=article.author,
            reviewer_name_snapshot="Jean Dupont",
            deadline=past_date,
        )

        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        late = response.context["late_reviews"]
        assert len(late) == 1
        assert late[0]["days_overdue"] == 5

    def test_upcoming_deadline_publication_date(self, client, user, membership, issue):
        import datetime

        from apps.issues.models import Issue as IssueModel

        future_date = datetime.date.today() + datetime.timedelta(days=30)
        IssueModel.objects.filter(pk=issue.pk).update(planned_publication_date=future_date)

        client.force_login(user)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": membership.journal.slug})
        )
        deadlines = response.context["upcoming_deadlines"]
        assert any(d["type"] == "issue_deadline" for d in deadlines)
        issue_deadline = next(d for d in deadlines if d["type"] == "issue_deadline")
        assert issue_deadline["date"] == future_date

    def test_other_journal_issues_not_in_context(self, client, db):
        from apps.accounts.models import User
        from apps.issues.models import Issue as IssueModel
        from apps.journals.models import Journal, Membership

        user1 = User.objects.create_user(email="u1@test.com", password="pass")
        journal1 = Journal.objects.create(name="Revue 1", slug="revue-1")
        journal2 = Journal.objects.create(name="Revue 2", slug="revue-2")
        Membership.objects.create(user=user1, journal=journal1)

        IssueModel.objects.create(
            journal=journal2,
            number="99",
            thematic_title="Numéro de l'autre revue",
            editor_name="Editor",
        )

        client.force_login(user1)
        response = client.get(
            reverse("journal_dashboard", kwargs={"slug": journal1.slug})
        )
        active_issues = response.context["active_issues"]
        assert all(i.journal_id == journal1.pk for i in active_issues)
