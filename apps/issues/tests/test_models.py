import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.issues.models import Issue


@pytest.mark.django_db
class TestIssue:
    def test_str(self, issue):
        assert "N°1" in str(issue)
        assert "Numéro de test" in str(issue)

    def test_unique_constraint_journal_number(self, issue, journal):
        with pytest.raises(IntegrityError):
            Issue.objects.create(
                journal=journal,
                number="1",
                thematic_title="Autre titre",
                editor_name="Autre éditeur",
            )

    def test_progress_no_articles(self, issue):
        assert issue.progress == 0

    def test_progress_partial(self, issue, contact):
        from apps.articles.models import Article

        Article.objects.create(issue=issue, title="A1")
        Article.objects.create(issue=issue, title="A2")
        Article.objects.filter(issue=issue, title="A1").update(state="validated")
        assert issue.progress == 50

    def test_progress_all_validated(self, issue, contact):
        from apps.articles.models import Article

        Article.objects.create(issue=issue, title="A1")
        Article.objects.filter(issue=issue).update(state="validated")
        assert issue.progress == 100


@pytest.mark.django_db
class TestIssueArchiveDates:
    def test_published_at_set_on_mark_as_published(self, issue):
        before = timezone.now()
        issue.accept()
        issue.save()
        issue.send_to_reviewers()
        issue.save()
        issue.reviews_received_return_to_authors()
        issue.save()
        issue.v2_received_final_check()
        issue.save()
        issue.send_to_publisher()
        issue.save()
        issue.mark_as_published()
        issue.save()
        assert issue.published_at is not None
        assert issue.published_at >= before

    def test_refused_at_set_on_refuse(self, issue):
        before = timezone.now()
        issue.refuse()
        issue.save()
        assert issue.refused_at is not None
        assert issue.refused_at >= before

    def test_published_at_not_overwritten_if_already_set(self, issue):
        from datetime import datetime, timezone as dt_tz
        existing = datetime(2024, 1, 1, tzinfo=dt_tz.utc)
        issue.published_at = existing
        issue.accept()
        issue.save()
        issue.send_to_reviewers()
        issue.save()
        issue.reviews_received_return_to_authors()
        issue.save()
        issue.v2_received_final_check()
        issue.save()
        issue.send_to_publisher()
        issue.save()
        issue.mark_as_published()
        issue.save()
        assert issue.published_at == existing

    def test_hook_not_triggered_on_other_transitions(self, issue):
        issue.accept()
        issue.save()
        assert issue.published_at is None
        assert issue.refused_at is None

    def test_refused_at_not_overwritten_if_already_set(self, issue):
        from datetime import datetime, timezone as dt_tz
        existing = datetime(2024, 1, 1, tzinfo=dt_tz.utc)
        issue.refused_at = existing
        issue.refuse()
        issue.save()
        assert issue.refused_at == existing

