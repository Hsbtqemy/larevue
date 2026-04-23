import pytest
from django.db import IntegrityError

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
