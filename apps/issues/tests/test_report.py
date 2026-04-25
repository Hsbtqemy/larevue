from unittest.mock import MagicMock, patch

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.accounts.models import User
from apps.articles.models import InternalNote
from apps.issues.models import Issue, IssueDocument
from apps.reviews.models import ReviewRequest


def _report_url(slug, issue_id):
    return reverse("issues:report", kwargs={"slug": slug, "issue_id": issue_id})


@pytest.fixture
def report_url(membership, issue):
    return _report_url(membership.journal.slug, issue.pk)


@pytest.fixture
def mock_wp():
    m = MagicMock()
    m.HTML.return_value.write_pdf.return_value = b"%PDF-1.4 fake"
    return m


@pytest.fixture
def received_favorable_review(review_request):
    ReviewRequest.objects.filter(pk=review_request.pk).update(
        state=ReviewRequest.State.RECEIVED,
        verdict=ReviewRequest.Verdict.FAVORABLE,
    )
    return ReviewRequest.objects.get(pk=review_request.pk)


@pytest.mark.django_db
class TestIssueReportAccess:
    def test_unauthenticated_redirects(self, client, journal, issue):
        res = client.get(_report_url(journal.slug, issue.pk))
        assert res.status_code == 302
        assert "/accounts/" in res["Location"]

    def test_non_member_gets_403(self, client, db, journal, issue):
        other = User.objects.create_user(
            email="stranger@test.com", password="pass",
            first_name="X", last_name="Y",
        )
        client.force_login(other)
        res = client.get(_report_url(journal.slug, issue.pk))
        assert res.status_code == 403

    def test_member_gets_200(self, client, user, membership, report_url):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", None):
            res = client.get(report_url)
        assert res.status_code == 200

    def test_nonexistent_issue_returns_404(self, client, user, membership):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", None):
            res = client.get(_report_url(membership.journal.slug, 99999))
        assert res.status_code == 404

    def test_content_type_pdf_when_weasyprint_available(self, client, user, membership, report_url, mock_wp):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", mock_wp):
            res = client.get(report_url)
        assert res["Content-Type"] == "application/pdf"

    def test_content_disposition_filename(self, client, user, membership, report_url, mock_wp):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", mock_wp):
            res = client.get(report_url)
        disposition = res["Content-Disposition"]
        assert "rapport_" in disposition
        assert ".pdf" in disposition

    def test_html_fallback_when_weasyprint_unavailable(self, client, user, membership, report_url):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", None):
            res = client.get(report_url)
        assert "text/html" in res["Content-Type"]


@pytest.mark.django_db
class TestIssueReportOptions:
    """Test that option flags control which sections appear in the HTML report."""

    def _get(self, client, user, report_url, **params):
        client.force_login(user)
        with patch("apps.issues.views.weasyprint", None):
            return client.get(report_url, params)

    def test_include_notes_1_shows_note_content(self, client, user, membership, report_url, issue):
        InternalNote.objects.create(issue=issue, content="Note confidentielle de test")
        res = self._get(client, user, report_url, include_notes=1)
        assert "Note confidentielle de test" in res.content.decode()

    def test_include_notes_0_hides_note_content(self, client, user, membership, report_url, issue):
        InternalNote.objects.create(issue=issue, content="Note confidentielle de test")
        res = self._get(client, user, report_url, include_notes=0)
        assert "Note confidentielle de test" not in res.content.decode()

    def test_include_articles_detail_1_shows_detail_section(self, client, user, membership, report_url, article):
        res = self._get(client, user, report_url, include_articles_detail=1)
        assert "Détail des articles" in res.content.decode()

    def test_include_articles_detail_0_hides_detail_section(self, client, user, membership, report_url, article):
        res = self._get(client, user, report_url, include_articles_detail=0)
        assert "Détail des articles" not in res.content.decode()

    def test_include_reviews_detail_1_shows_verdict(self, client, user, membership, report_url, received_favorable_review):
        res = self._get(client, user, report_url, include_articles_detail=1, include_reviews_detail=1)
        assert "Favorable" in res.content.decode()

    def test_include_reviews_detail_0_hides_verdict(self, client, user, membership, report_url, received_favorable_review):
        res = self._get(client, user, report_url, include_articles_detail=1, include_reviews_detail=0)
        assert "Favorable" not in res.content.decode()

    def test_include_documents_1_shows_document_name(self, client, user, membership, report_url, issue):
        IssueDocument.objects.create(
            issue=issue,
            name="Budget prévisionnel 2026",
            file=ContentFile(b"fake", name="budget.pdf"),
            uploaded_by=user,
        )
        res = self._get(client, user, report_url, include_documents=1)
        assert "Budget prévisionnel 2026" in res.content.decode()

    def test_include_documents_0_hides_document_name(self, client, user, membership, report_url, issue):
        IssueDocument.objects.create(
            issue=issue,
            name="Budget prévisionnel 2026",
            file=ContentFile(b"fake", name="budget.pdf"),
            uploaded_by=user,
        )
        res = self._get(client, user, report_url, include_documents=0)
        assert "Budget prévisionnel 2026" not in res.content.decode()
