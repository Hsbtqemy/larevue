import pytest
from django.urls import reverse

from apps.articles.models import Article, InternalNote
from apps.issues.models import Issue


def _url(journal, issue):
    return reverse("issues:transition", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _post(client, url, transition, note=""):
    return client.post(url, {"transition": transition, "note": note})


@pytest.fixture
def accepted_issue(issue):
    issue.accept()
    issue.save()
    return issue


@pytest.fixture
def in_production_issue(accepted_issue):
    accepted_issue.start_production()
    accepted_issue.save()
    return accepted_issue


@pytest.fixture
def sent_issue(in_production_issue, article):
    article.send_to_review()
    article.mark_reviews_received()
    article.validate()
    article.save()
    in_production_issue.send_to_publisher()
    in_production_issue.save()
    return in_production_issue


@pytest.mark.django_db
class TestIssueTransitionView:

    # ── auth / membership ─────────────────────────────────────────────

    def test_requires_login(self, client, journal, issue):
        res = _post(client, _url(journal, issue), "accept")
        assert res.status_code == 302

    def test_non_member_gets_403(self, client, user, journal, issue):
        client.force_login(user)
        res = _post(client, _url(journal, issue), "accept")
        assert res.status_code == 403

    # ── accept ────────────────────────────────────────────────────────

    def test_accept_changes_state(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "accept")
        assert Issue.objects.get(pk=issue.pk).state == Issue.State.ACCEPTED

    def test_accept_returns_redirect_url(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _post(client, _url(journal, issue), "accept")
        assert res.status_code == 200
        assert "redirect_url" in res.json()

    def test_accept_creates_audit_note(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "accept")
        assert InternalNote.objects.filter(issue=issue, is_automatic=True).exists()

    def test_accept_includes_actor_name_in_note(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "accept")
        note = InternalNote.objects.get(issue=issue, is_automatic=True)
        assert user.first_name in note.content or user.email in note.content

    def test_accept_with_user_note_appended(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "accept", note="Très bonne thématique")
        note = InternalNote.objects.get(issue=issue, is_automatic=True)
        assert "Très bonne thématique" in note.content

    def test_accept_from_wrong_state_returns_400(self, client, user, membership, journal, accepted_issue):
        client.force_login(user)
        res = _post(client, _url(journal, accepted_issue), "accept")
        assert res.status_code == 400

    # ── refuse ────────────────────────────────────────────────────────

    def test_refuse_changes_state(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "refuse")
        assert Issue.objects.get(pk=issue.pk).state == Issue.State.REFUSED

    def test_refuse_creates_audit_note(self, client, user, membership, journal, issue):
        client.force_login(user)
        _post(client, _url(journal, issue), "refuse")
        assert InternalNote.objects.filter(issue=issue, is_automatic=True).exists()

    # ── start_production ──────────────────────────────────────────────

    def test_start_production_changes_state(self, client, user, membership, journal, accepted_issue):
        client.force_login(user)
        _post(client, _url(journal, accepted_issue), "start_production")
        assert Issue.objects.get(pk=accepted_issue.pk).state == Issue.State.IN_PRODUCTION

    # ── send_to_publisher preconditions ───────────────────────────────

    def test_send_to_publisher_empty_issue_returns_400(self, client, user, membership, journal, in_production_issue):
        client.force_login(user)
        res = _post(client, _url(journal, in_production_issue), "send_to_publisher")
        assert res.status_code == 400
        assert "article" in res.json()["error"].lower()

    def test_send_to_publisher_not_all_validated_returns_400(self, client, user, membership, journal, in_production_issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, in_production_issue), "send_to_publisher")
        assert res.status_code == 400
        data = res.json()
        assert "0/1" in data["error"] or "validé" in data["error"]

    def test_send_to_publisher_all_validated_succeeds(self, client, user, membership, journal, in_production_issue, article):
        Article.objects.filter(pk=article.pk).update(state=Article.State.VALIDATED)
        client.force_login(user)
        res = _post(client, _url(journal, in_production_issue), "send_to_publisher")
        assert res.status_code == 200
        assert Issue.objects.get(pk=in_production_issue.pk).state == Issue.State.SENT_TO_PUBLISHER

    # ── mark_as_published ─────────────────────────────────────────────

    def test_mark_as_published_changes_state(self, client, user, membership, journal, sent_issue):
        client.force_login(user)
        _post(client, _url(journal, sent_issue), "mark_as_published")
        assert Issue.objects.get(pk=sent_issue.pk).state == Issue.State.PUBLISHED

    def test_mark_as_published_enters_archived_states(self, client, user, membership, journal, sent_issue):
        client.force_login(user)
        _post(client, _url(journal, sent_issue), "mark_as_published")
        assert Issue.objects.get(pk=sent_issue.pk).state in Issue.ARCHIVED_STATES

    # ── rollbacks ─────────────────────────────────────────────────────

    def test_reopen_for_review(self, client, user, membership, journal, accepted_issue):
        client.force_login(user)
        _post(client, _url(journal, accepted_issue), "reopen_for_review")
        assert Issue.objects.get(pk=accepted_issue.pk).state == Issue.State.UNDER_REVIEW

    def test_pause_production(self, client, user, membership, journal, in_production_issue):
        client.force_login(user)
        _post(client, _url(journal, in_production_issue), "pause_production")
        assert Issue.objects.get(pk=in_production_issue.pk).state == Issue.State.ACCEPTED

    def test_recall_from_publisher(self, client, user, membership, journal, sent_issue):
        client.force_login(user)
        _post(client, _url(journal, sent_issue), "recall_from_publisher")
        assert Issue.objects.get(pk=sent_issue.pk).state == Issue.State.IN_PRODUCTION

    def test_unpublish(self, client, user, membership, journal, sent_issue):
        sent_issue.mark_as_published()
        sent_issue.save()
        client.force_login(user)
        _post(client, _url(journal, sent_issue), "unpublish")
        assert Issue.objects.get(pk=sent_issue.pk).state == Issue.State.SENT_TO_PUBLISHER

    # ── unknown / disallowed transition ───────────────────────────────

    def test_unknown_transition_returns_400(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _post(client, _url(journal, issue), "fly_to_moon")
        assert res.status_code == 400

    # ── context: transitions in view context ──────────────────────────

    def test_context_primary_transition_for_under_review(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})).context
        assert ctx["transitions"]["primary"]["name"] == "accept"

    def test_context_secondary_transition_for_under_review(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})).context
        secondary_names = [t["name"] for t in ctx["transitions"]["secondary"]]
        assert "refuse" in secondary_names

    def test_context_no_primary_for_refused(self, client, user, membership, journal, issue):
        issue.refuse()
        issue.save()
        client.force_login(user)
        ctx = client.get(reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})).context
        assert ctx["transitions"]["primary"] is None

    def test_context_send_to_publisher_disabled_when_no_articles(self, client, user, membership, journal, in_production_issue):
        client.force_login(user)
        ctx = client.get(reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": in_production_issue.pk})).context
        primary = ctx["transitions"]["primary"]
        assert primary["name"] == "send_to_publisher"
        assert primary["enabled"] is False
        assert primary["disabled_reason"]
