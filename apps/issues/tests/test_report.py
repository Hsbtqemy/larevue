from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.articles.models import InternalNote
from apps.issues.models import Issue


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
