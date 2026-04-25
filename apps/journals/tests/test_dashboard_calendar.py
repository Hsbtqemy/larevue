import datetime

import pytest
from django.urls import reverse

from apps.issues.models import Issue
from apps.journals.views import _build_calendar_events


def _dashboard_url(slug):
    return reverse("journal_dashboard", kwargs={"slug": slug})


@pytest.mark.django_db
class TestBuildCalendarEvents:
    def test_all_six_deadline_fields_yield_six_events(self, journal):
        Issue.objects.create(
            journal=journal, number="1", thematic_title="Test", editor_name="Éd.",
            deadline_articles=datetime.date(2026, 6, 1),
            deadline_reviews=datetime.date(2026, 6, 15),
            deadline_v2=datetime.date(2026, 7, 1),
            deadline_final_check=datetime.date(2026, 7, 15),
            deadline_sent_to_publisher=datetime.date(2026, 8, 1),
            planned_publication_date=datetime.date(2026, 9, 1),
        )
        assert len(_build_calendar_events(journal)) == 6

    def test_archived_issue_excluded(self, journal):
        issue = Issue.objects.create(
            journal=journal, number="2", thematic_title="Archivé", editor_name="Éd.",
            deadline_articles=datetime.date(2026, 6, 1),
        )
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        assert len(_build_calendar_events(journal)) == 0

    def test_null_deadlines_skipped(self, journal):
        Issue.objects.create(
            journal=journal, number="3", thematic_title="Partiel", editor_name="Éd.",
            deadline_articles=datetime.date(2026, 6, 1),
        )
        events = _build_calendar_events(journal)
        assert len(events) == 1
        assert events[0]["type"] == "articles"

    def test_review_request_expected_included(self, journal, review_request):
        events = _build_calendar_events(journal)
        assert any(e["type"] == "review_request" for e in events)

    def test_review_request_on_archived_issue_excluded(self, journal, review_request):
        Issue.objects.filter(pk=review_request.article.issue.pk).update(state=Issue.State.PUBLISHED)
        events = _build_calendar_events(journal)
        assert not any(e["type"] == "review_request" for e in events)

    def test_event_has_required_keys(self, journal):
        Issue.objects.create(
            journal=journal, number="4", thematic_title="Keys", editor_name="Éd.",
            deadline_articles=datetime.date(2026, 6, 1),
        )
        events = _build_calendar_events(journal)
        assert events[0].keys() >= {"date", "type", "label", "url"}


@pytest.mark.django_db
class TestDashboardCalendarContext:
    def test_calendar_events_in_context(self, client, user, membership):
        client.force_login(user)
        res = client.get(_dashboard_url(membership.journal.slug))
        assert "calendar_events" in res.context
        assert isinstance(res.context["calendar_events"], list)

    def test_today_iso_in_context(self, client, user, membership):
        client.force_login(user)
        res = client.get(_dashboard_url(membership.journal.slug))
        assert "today_iso" in res.context
        datetime.date.fromisoformat(res.context["today_iso"])
