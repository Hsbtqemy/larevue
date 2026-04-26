import datetime
from datetime import timezone as dt_tz

import pytest
from django.urls import reverse

from apps.issues.models import Issue as IssueModel


def _url(journal):
    return reverse("journal_archives", kwargs={"slug": journal.slug})


@pytest.mark.django_db
class TestJournalArchivesAccess:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_url(journal))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_member_can_access(self, client, user, membership):
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert response.status_code == 200

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User
        from apps.journals.models import Journal, Membership

        other_journal = Journal.objects.create(name="Autre revue", slug="autre-revue")
        owner = User.objects.create_user(email="owner@example.com", password="pass")
        Membership.objects.create(user=owner, journal=other_journal)

        intruder = User.objects.create_user(email="intrus@example.com", password="pass")
        client.force_login(intruder)
        response = client.get(_url(other_journal))
        assert response.status_code == 403

    def test_nonexistent_slug_returns_404(self, client, user):
        client.force_login(user)
        response = client.get(reverse("journal_archives", kwargs={"slug": "nexiste-pas"}))
        assert response.status_code == 404


@pytest.mark.django_db
class TestJournalArchivesContent:
    def test_active_issue_not_shown(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert issue.thematic_title not in response.content.decode()

    def test_published_issue_shown(self, client, user, membership, issue):
        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.PUBLISHED)
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert issue.thematic_title in response.content.decode()

    def test_refused_issue_shown(self, client, user, membership, issue):
        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.REFUSED)
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert issue.thematic_title in response.content.decode()

    def test_context_keys(self, client, user, membership):
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert "years_groups" in response.context
        assert "total_count" in response.context

    def test_total_count(self, client, user, membership, journal):
        IssueModel.objects.create(journal=journal, number="2", thematic_title="B", editor_name="Ed", state=IssueModel.State.PUBLISHED)
        IssueModel.objects.create(journal=journal, number="3", thematic_title="C", editor_name="Ed", state=IssueModel.State.REFUSED)
        client.force_login(user)
        response = client.get(_url(journal))
        assert response.context["total_count"] == 2

    def test_empty_state_shown_when_no_archives(self, client, user, membership):
        client.force_login(user)
        response = client.get(_url(membership.journal))
        assert "Aucun numéro archivé" in response.content.decode()


@pytest.mark.django_db
class TestJournalArchivesGrouping:
    def test_year_grouping_order(self, client, user, membership, journal):
        IssueModel.objects.filter(journal=journal).delete()
        i1 = IssueModel.objects.create(journal=journal, number="10", thematic_title="Ancien", editor_name="Ed")
        i2 = IssueModel.objects.create(journal=journal, number="11", thematic_title="Recent", editor_name="Ed")
        IssueModel.objects.filter(pk=i1.pk).update(
            state=IssueModel.State.PUBLISHED,
            published_at=datetime.datetime(2023, 5, 1, tzinfo=dt_tz.utc),
        )
        IssueModel.objects.filter(pk=i2.pk).update(
            state=IssueModel.State.PUBLISHED,
            published_at=datetime.datetime(2024, 3, 1, tzinfo=dt_tz.utc),
        )
        client.force_login(user)
        response = client.get(_url(journal))
        years = [y for y, _ in response.context["years_groups"]]
        assert years == sorted(years, reverse=True)
        assert 2024 in years
        assert 2023 in years

    def test_issues_in_correct_year_bucket(self, client, user, membership, journal):
        IssueModel.objects.filter(journal=journal).delete()
        issue = IssueModel.objects.create(journal=journal, number="5", thematic_title="Bucket test", editor_name="Ed")
        IssueModel.objects.filter(pk=issue.pk).update(
            state=IssueModel.State.PUBLISHED,
            published_at=datetime.datetime(2025, 9, 15, tzinfo=dt_tz.utc),
        )
        client.force_login(user)
        response = client.get(_url(journal))
        for year, issues in response.context["years_groups"]:
            if year == 2025:
                assert any(i.pk == issue.pk for i in issues)
                return
        pytest.fail("Year 2025 not found in groups")


@pytest.mark.django_db
class TestJournalArchivesStats:
    def test_article_count_annotation(self, client, user, membership, journal):
        from apps.articles.models import Article

        issue = IssueModel.objects.create(journal=journal, number="20", thematic_title="Stats", editor_name="Ed")
        Article.objects.create(issue=issue, title="Art1")
        Article.objects.create(issue=issue, title="Art2")
        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.PUBLISHED)

        client.force_login(user)
        response = client.get(_url(journal))
        archived = _find_issue(response.context["years_groups"], issue.pk)
        assert archived.article_count == 2

    def test_reviews_received_count_annotation(self, client, user, membership, journal):
        from apps.articles.models import Article, ArticleVersion
        from apps.contacts.models import Contact
        from apps.reviews.models import ReviewRequest
        from django.core.files.base import ContentFile

        issue = IssueModel.objects.create(journal=journal, number="21", thematic_title="Review stats", editor_name="Ed")
        art = Article.objects.create(issue=issue, title="Art")
        reviewer = Contact.objects.create(journal=journal, first_name="R", last_name="R", email="r@r.com")
        version = ArticleVersion.objects.create(
            article=art,
            file=ContentFile(b"pdf", name="v.pdf"),
            uploaded_by=user,
        )
        ReviewRequest.objects.create(
            article=art,
            article_version=version,
            reviewer=reviewer,
            reviewer_name_snapshot=reviewer.full_name,
            deadline=datetime.date.today(),
            state=ReviewRequest.State.RECEIVED,
        )
        ReviewRequest.objects.create(
            article=art,
            article_version=version,
            reviewer=reviewer,
            reviewer_name_snapshot=reviewer.full_name,
            deadline=datetime.date.today(),
            state=ReviewRequest.State.SENT,
        )
        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.PUBLISHED)

        client.force_login(user)
        response = client.get(_url(journal))
        archived = _find_issue(response.context["years_groups"], issue.pk)
        assert archived.reviews_received_count == 1


def _export_url(journal):
    return reverse("journal_archives_export", kwargs={"slug": journal.slug})


@pytest.mark.django_db
class TestJournalArchivesExport:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_export_url(journal))
        assert response.status_code == 302

    def test_returns_csv(self, client, user, membership):
        client.force_login(user)
        response = client.get(_export_url(membership.journal))
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        assert "attachment" in response["Content-Disposition"]

    def test_csv_contains_header(self, client, user, membership):
        client.force_login(user)
        response = client.get(_export_url(membership.journal))
        content = response.content.decode("utf-8-sig")
        assert "Titre thématique" in content
        assert "Relectures reçues" in content

    def test_csv_includes_published_issue(self, client, user, membership, issue):
        IssueModel.objects.filter(pk=issue.pk).update(state=IssueModel.State.PUBLISHED)
        client.force_login(user)
        response = client.get(_export_url(membership.journal))
        assert issue.thematic_title in response.content.decode("utf-8-sig")

    def test_csv_excludes_active_issue(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(_export_url(membership.journal))
        assert issue.thematic_title not in response.content.decode("utf-8-sig")

    def test_state_filter_published_only(self, client, user, membership, journal):
        IssueModel.objects.filter(journal=journal).delete()
        pub = IssueModel.objects.create(journal=journal, number="30", thematic_title="Publié", editor_name="Ed")
        ref = IssueModel.objects.create(journal=journal, number="31", thematic_title="Refusé", editor_name="Ed")
        IssueModel.objects.filter(pk=pub.pk).update(state=IssueModel.State.PUBLISHED)
        IssueModel.objects.filter(pk=ref.pk).update(state=IssueModel.State.REFUSED)
        client.force_login(user)
        response = client.get(_export_url(journal) + "?state=published")
        content = response.content.decode("utf-8-sig")
        assert "Publié" in content
        assert "Refusé" not in content

    def test_state_filter_refused_only(self, client, user, membership, journal):
        IssueModel.objects.filter(journal=journal).delete()
        pub = IssueModel.objects.create(journal=journal, number="32", thematic_title="PubliéB", editor_name="Ed")
        ref = IssueModel.objects.create(journal=journal, number="33", thematic_title="RefuséB", editor_name="Ed")
        IssueModel.objects.filter(pk=pub.pk).update(state=IssueModel.State.PUBLISHED)
        IssueModel.objects.filter(pk=ref.pk).update(state=IssueModel.State.REFUSED)
        client.force_login(user)
        response = client.get(_export_url(journal) + "?state=refused")
        content = response.content.decode("utf-8-sig")
        assert "RefuséB" in content
        assert "PubliéB" not in content

    def test_filename_includes_journal_slug(self, client, user, membership):
        client.force_login(user)
        response = client.get(_export_url(membership.journal))
        assert membership.journal.slug in response["Content-Disposition"]


def _find_issue(years_groups, pk):
    for _year, issues in years_groups:
        for issue in issues:
            if issue.pk == pk:
                return issue
    pytest.fail(f"Issue pk={pk} not found in years_groups")
