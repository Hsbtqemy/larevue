import pytest
from django.urls import reverse

from apps.articles.models import Article, InternalNote
from apps.issues.models import Issue


def _url(journal, issue, article):
    return reverse(
        "articles:transition",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _post(client, url, transition, note=""):
    return client.post(url, {"transition": transition, "note": note})


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def in_review_article(article):
    article.send_to_review()
    article.save()
    return article


@pytest.fixture
def reviews_received_article(in_review_article):
    in_review_article.mark_reviews_received()
    in_review_article.save()
    return in_review_article


@pytest.fixture
def in_author_revision_article(reviews_received_article):
    reviews_received_article.send_to_author()
    reviews_received_article.save()
    return reviews_received_article


@pytest.fixture
def revised_article(in_author_revision_article):
    in_author_revision_article.mark_as_revised()
    in_author_revision_article.save()
    return in_author_revision_article


@pytest.fixture
def validated_article(reviews_received_article):
    reviews_received_article.validate()
    reviews_received_article.save()
    return reviews_received_article


@pytest.fixture
def archived_issue(issue):
    issue.accept()
    issue.send_to_reviewers()
    issue.reviews_received_return_to_authors()
    issue.v2_received_final_check()
    Article.objects.filter(issue=issue).update(state=Article.State.VALIDATED)
    issue.send_to_publisher()
    issue.mark_as_published()
    issue.save()
    return issue


@pytest.mark.django_db
class TestArticleTransitionView:

    # ── auth / membership ─────────────────────────────────────────────────────

    def test_requires_login(self, client, journal, issue, article):
        res = _post(client, _url(journal, issue, article), "send_to_review")
        assert res.status_code == 302

    def test_non_member_gets_403(self, client, user, journal, issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, issue, article), "send_to_review")
        assert res.status_code == 403

    # ── archived issue blocks all transitions ─────────────────────────────────

    def test_archived_issue_returns_403(self, client, user, membership, journal, archived_issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, archived_issue, article), "send_to_review")
        assert res.status_code == 403

    # ── send_to_review (from received) ───────────────────────────────────────

    def test_send_to_review_changes_state(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _post(client, _url(journal, issue, article), "send_to_review")
        assert Article.objects.get(pk=article.pk).state == Article.State.IN_REVIEW

    def test_send_to_review_returns_redirect_url(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, issue, article), "send_to_review")
        assert res.status_code == 200
        assert "redirect_url" in res.json()

    def test_send_to_review_creates_audit_note(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _post(client, _url(journal, issue, article), "send_to_review")
        assert InternalNote.objects.filter(article=article, is_automatic=True).exists()

    def test_send_to_review_includes_actor_name_in_note(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _post(client, _url(journal, issue, article), "send_to_review")
        note = InternalNote.objects.get(article=article, is_automatic=True)
        assert user.first_name in note.content or user.email in note.content

    def test_send_to_review_with_user_note_appended(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _post(client, _url(journal, issue, article), "send_to_review", note="Deux relecteurs minimum")
        note = InternalNote.objects.get(article=article, is_automatic=True)
        assert "Deux relecteurs minimum" in note.content

    def test_send_to_review_from_wrong_state_returns_400(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        res = _post(client, _url(journal, issue, in_review_article), "send_to_review")
        assert res.status_code == 400

    # ── send_to_review (from revised) ────────────────────────────────────────

    def test_send_to_review_from_revised_changes_state(self, client, user, membership, journal, issue, revised_article):
        client.force_login(user)
        _post(client, _url(journal, issue, revised_article), "send_to_review")
        assert Article.objects.get(pk=revised_article.pk).state == Article.State.IN_REVIEW

    # ── cancel_review ─────────────────────────────────────────────────────────

    def test_cancel_review_changes_state(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        _post(client, _url(journal, issue, in_review_article), "cancel_review")
        assert Article.objects.get(pk=in_review_article.pk).state == Article.State.RECEIVED

    def test_cancel_review_creates_audit_note(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        _post(client, _url(journal, issue, in_review_article), "cancel_review")
        assert InternalNote.objects.filter(article=in_review_article, is_automatic=True).exists()

    # ── mark_reviews_received ─────────────────────────────────────────────────

    def test_mark_reviews_received_changes_state(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        _post(client, _url(journal, issue, in_review_article), "mark_reviews_received")
        assert Article.objects.get(pk=in_review_article.pk).state == Article.State.REVIEWS_RECEIVED

    # ── send_to_author ────────────────────────────────────────────────────────

    def test_send_to_author_changes_state(self, client, user, membership, journal, issue, reviews_received_article):
        client.force_login(user)
        _post(client, _url(journal, issue, reviews_received_article), "send_to_author")
        assert Article.objects.get(pk=reviews_received_article.pk).state == Article.State.IN_AUTHOR_REVISION

    # ── validate ──────────────────────────────────────────────────────────────

    def test_validate_from_reviews_received_changes_state(self, client, user, membership, journal, issue, reviews_received_article):
        client.force_login(user)
        _post(client, _url(journal, issue, reviews_received_article), "validate")
        assert Article.objects.get(pk=reviews_received_article.pk).state == Article.State.VALIDATED

    def test_validate_from_revised_changes_state(self, client, user, membership, journal, issue, revised_article):
        client.force_login(user)
        _post(client, _url(journal, issue, revised_article), "validate")
        assert Article.objects.get(pk=revised_article.pk).state == Article.State.VALIDATED

    def test_validate_from_wrong_state_returns_400(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, issue, article), "validate")
        assert res.status_code == 400

    # ── mark_as_revised ───────────────────────────────────────────────────────

    def test_mark_as_revised_changes_state(self, client, user, membership, journal, issue, in_author_revision_article):
        client.force_login(user)
        _post(client, _url(journal, issue, in_author_revision_article), "mark_as_revised")
        assert Article.objects.get(pk=in_author_revision_article.pk).state == Article.State.REVISED

    # ── request_more_revision ─────────────────────────────────────────────────

    def test_request_more_revision_changes_state(self, client, user, membership, journal, issue, revised_article):
        client.force_login(user)
        _post(client, _url(journal, issue, revised_article), "request_more_revision")
        assert Article.objects.get(pk=revised_article.pk).state == Article.State.IN_AUTHOR_REVISION

    # ── unknown / disallowed transition ───────────────────────────────────────

    def test_unknown_transition_returns_400(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _post(client, _url(journal, issue, article), "fly_to_moon")
        assert res.status_code == 400

    # ── context: transitions in view context ──────────────────────────────────

    def test_context_primary_transition_for_received(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        ctx = client.get(
            reverse("articles:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk})
        ).context
        primary_names = [t["name"] for t in ctx["transitions"]["primary"]]
        assert "send_to_review" in primary_names

    def test_context_primary_transition_for_in_review(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        ctx = client.get(
            reverse("articles:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": in_review_article.pk})
        ).context
        primary_names = [t["name"] for t in ctx["transitions"]["primary"]]
        assert "mark_reviews_received" in primary_names

    def test_context_cancel_review_in_advanced_for_in_review(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        ctx = client.get(
            reverse("articles:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": in_review_article.pk})
        ).context
        advanced_names = [t["name"] for t in ctx["transitions"]["advanced"]]
        assert "cancel_review" in advanced_names

    def test_context_no_primary_for_archived_issue(self, client, user, membership, journal, archived_issue, article):
        client.force_login(user)
        ctx = client.get(
            reverse("articles:detail", kwargs={"slug": journal.slug, "issue_id": archived_issue.pk, "article_id": article.pk})
        ).context
        assert ctx["transitions"]["primary"] == []
        assert ctx["transitions"]["advanced"] == []
