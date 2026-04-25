import datetime

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.articles.models import Article, ArticleVersion, InternalNote
from apps.contacts.models import Contact
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


# ──────────────────────────── URL helpers ────────────────────────────

def _detail_url(journal, issue, article):
    return reverse(
        "articles:detail",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _patch_url(journal, issue, article):
    return reverse(
        "articles:patch",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _edit_url(journal, issue, article):
    return reverse(
        "articles:edit",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _delete_url(journal, issue, article):
    return reverse(
        "articles:delete",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _note_url(journal, issue, article):
    return reverse(
        "articles:note_create",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _json_post(client, url, payload):
    import json
    return client.post(url, data=json.dumps(payload), content_type="application/json")


# ──────────────────────────── TestArticleDetailView ────────────────────────────

@pytest.mark.django_db
class TestArticleDetailView:
    def test_requires_login(self, client, journal, issue, article):
        res = client.get(_detail_url(journal, issue, article))
        assert res.status_code == 302

    def test_non_member_forbidden(self, client, journal, issue, article):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.get(_detail_url(journal, issue, article))
        assert res.status_code == 403

    def test_wrong_journal_is_404(self, client, user, membership, journal, issue, article):
        from apps.journals.models import Journal, Membership
        other_journal = Journal.objects.create(name="Autre", slug="autre")
        Membership.objects.create(user=user, journal=other_journal)
        client.force_login(user)
        url = reverse(
            "articles:detail",
            kwargs={"slug": "autre", "issue_id": issue.pk, "article_id": article.pk},
        )
        res = client.get(url)
        assert res.status_code == 404

    def test_wrong_issue_id_in_url_is_404(self, client, user, membership, journal, issue, article):
        from apps.issues.models import Issue
        other_issue = Issue.objects.create(
            journal=journal, number="99", thematic_title="Autre numéro", editor_name="X"
        )
        client.force_login(user)
        url = reverse(
            "articles:detail",
            kwargs={"slug": journal.slug, "issue_id": other_issue.pk, "article_id": article.pk},
        )
        res = client.get(url)
        assert res.status_code == 404

    def test_ok(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        assert client.get(_detail_url(journal, issue, article)).status_code == 200

    def test_context_keys_present(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue, article)).context
        for key in ("article", "issue", "journal", "internal_notes", "is_archived"):
            assert key in ctx

    def test_is_archived_false_for_active_issue(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue, article)).context
        assert ctx["is_archived"] is False

    def test_is_archived_true_for_published_issue(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue, article)).context
        assert ctx["is_archived"] is True

    def test_version_and_review_counts(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue, article)).context
        assert ctx["version_count"] == 0
        assert ctx["review_request_count"] == 0


# ──────────────────────────── TestArticlePatchView ────────────────────────────

@pytest.mark.django_db
class TestArticlePatchView:
    def test_requires_login(self, client, journal, issue, article):
        res = _json_post(client, _patch_url(journal, issue, article), {"field": "title", "value": "New"})
        assert res.status_code == 302

    def test_patch_title_valid(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue, article), {"field": "title", "value": "Nouveau titre"})
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert Article.objects.get(pk=article.pk).title == "Nouveau titre"

    def test_patch_creates_audit_note(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _json_post(client, _patch_url(journal, issue, article), {"field": "title", "value": "Avec note"})
        note = InternalNote.objects.filter(article=article, is_automatic=True).last()
        assert note is not None
        assert "Avec note" in note.content

    def test_patch_author_valid(self, client, user, membership, journal, issue, article, contact):
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue, article),
            {"field": "author", "value": str(contact.pk)},
        )
        assert res.status_code == 200
        assert Article.objects.get(pk=article.pk).author_id == contact.pk

    def test_patch_author_other_journal_returns_400(self, client, user, membership, journal, issue, article):
        from apps.journals.models import Journal
        other_journal = Journal.objects.create(name="Autre", slug="autrej")
        other_contact = Contact.objects.create(journal=other_journal, first_name="X", last_name="Y")
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue, article),
            {"field": "author", "value": str(other_contact.pk)},
        )
        assert res.status_code == 400

    def test_patch_author_clear(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue, article), {"field": "author", "value": ""})
        assert res.status_code == 200
        assert Article.objects.get(pk=article.pk).author_id is None

    def test_patch_article_type_valid(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue, article),
            {"field": "article_type", "value": "introduction"},
        )
        assert res.status_code == 200
        assert Article.objects.get(pk=article.pk).article_type == "introduction"

    def test_patch_abstract_valid(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue, article),
            {"field": "abstract", "value": "Un résumé de l'article."},
        )
        assert res.status_code == 200
        assert Article.objects.get(pk=article.pk).abstract == "Un résumé de l'article."

    def test_patch_article_type_invalid_value(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue, article),
            {"field": "article_type", "value": "invalid_type"},
        )
        assert res.status_code == 400

    def test_patch_forbidden_field(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue, article), {"field": "state", "value": "validated"})
        assert res.status_code == 400

    def test_patch_archived_issue_forbidden(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue, article), {"field": "title", "value": "X"})
        assert res.status_code == 403

    def test_patch_malformed_json(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(
            _patch_url(journal, issue, article),
            data="not-json",
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_patch_wrong_issue_id_is_404(self, client, user, membership, journal, issue, article):
        other_issue = Issue.objects.create(
            journal=journal, number="99", thematic_title="Autre", editor_name="X"
        )
        client.force_login(user)
        url = reverse(
            "articles:patch",
            kwargs={"slug": journal.slug, "issue_id": other_issue.pk, "article_id": article.pk},
        )
        res = _json_post(client, url, {"field": "title", "value": "X"})
        assert res.status_code == 404


# ──────────────────────────── TestArticleEditView ────────────────────────────

@pytest.mark.django_db
class TestArticleEditView:
    def _form_data(self, article, **overrides):
        data = {
            "title": article.title,
            "article_type": article.article_type,
        }
        data.update(overrides)
        return data

    def test_valid_edit_saves_and_returns_redirect(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_edit_url(journal, issue, article), self._form_data(article, title="Nouveau"))
        assert res.status_code == 200
        data = res.json()
        assert "redirect_url" in data
        assert Article.objects.get(pk=article.pk).title == "Nouveau"

    def test_invalid_edit_returns_errors(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_edit_url(journal, issue, article), self._form_data(article, title=""))
        assert res.status_code == 400
        assert "title" in res.json()["errors"]

    def test_archived_issue_forbidden(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.REFUSED)
        client.force_login(user)
        res = client.post(_edit_url(journal, issue, article), self._form_data(article))
        assert res.status_code == 403

    def test_requires_login(self, client, journal, issue, article):
        res = client.post(_edit_url(journal, issue, article), {})
        assert res.status_code == 302


# ──────────────────────────── TestArticleDeleteView ────────────────────────────

@pytest.mark.django_db
class TestArticleDeleteView:
    def test_soft_deletes_article(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.delete(_delete_url(journal, issue, article))
        assert res.status_code == 200
        assert not Article.objects.filter(pk=article.pk).exists()

    def test_article_still_in_all_objects(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        client.delete(_delete_url(journal, issue, article))
        assert Article.all_objects.filter(pk=article.pk).exists()

    def test_redirect_url_points_to_issue(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        data = client.delete(_delete_url(journal, issue, article)).json()
        expected = reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})
        assert data["redirect_url"] == expected

    def test_archived_issue_forbidden(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.delete(_delete_url(journal, issue, article))
        assert res.status_code == 403

    def test_non_member_forbidden(self, client, journal, issue, article):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other4@test.com", password="pass")
        client.force_login(other)
        res = client.delete(_delete_url(journal, issue, article))
        assert res.status_code == 403

    def test_requires_login(self, client, journal, issue, article):
        res = client.delete(_delete_url(journal, issue, article))
        assert res.status_code == 302


# ──────────────────────────── TestArticleNoteCreateView ────────────────────────────

@pytest.mark.django_db
class TestArticleNoteCreateView:
    def test_creates_note(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_note_url(journal, issue, article), {"content": "Une note"})
        assert res.status_code == 200
        assert InternalNote.objects.filter(article=article, content="Une note").exists()

    def test_returns_partial_html(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_note_url(journal, issue, article), {"content": "Note HTML"})
        assert res.status_code == 200
        assert b"note-item" in res.content

    def test_note_is_not_automatic(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        client.post(_note_url(journal, issue, article), {"content": "Manuelle"})
        note = InternalNote.objects.get(article=article)
        assert not note.is_automatic

    def test_empty_content_returns_400(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_note_url(journal, issue, article), {"content": "  "})
        assert res.status_code == 400

    def test_archived_issue_forbidden(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.post(_note_url(journal, issue, article), {"content": "Note"})
        assert res.status_code == 403

    def test_requires_login(self, client, journal, issue, article):
        res = client.post(_note_url(journal, issue, article), {"content": "Note"})
        assert res.status_code == 302


# ──────────────────────────── IssuePatchView régression ────────────────────────────

@pytest.mark.django_db
class TestIssuePatchViewRegression:
    """Vérifie qu'IssuePatchView fonctionne toujours après héritage de JournalOwnedPatchView."""

    def test_patch_allowed_field(self, client, user, membership, journal, issue):
        import json
        client.force_login(user)
        url = reverse("issues:patch", kwargs={"slug": journal.slug, "issue_id": issue.pk})
        res = client.post(url, data=json.dumps({"field": "number", "value": "42"}), content_type="application/json")
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).number == "42"

    def test_patch_creates_audit_note(self, client, user, membership, journal, issue):
        import json
        client.force_login(user)
        url = reverse("issues:patch", kwargs={"slug": journal.slug, "issue_id": issue.pk})
        client.post(url, data=json.dumps({"field": "thematic_title", "value": "Refacto"}), content_type="application/json")
        note = InternalNote.objects.filter(issue=issue, is_automatic=True).last()
        assert note is not None
        assert "Refacto" in note.content


# ──────────────────────────── URL helpers E2 ────────────────────────────

def _version_download_url(journal, issue, article, version):
    return reverse("articles:version_download", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk, "version_id": version.pk})

def _review_create_url(journal, issue, article):
    return reverse("articles:review_create", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk})

def _review_receive_url(journal, issue, article, review):
    return reverse("articles:review_receive", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk, "review_id": review.pk})

def _review_delete_url(journal, issue, article, review):
    return reverse("articles:review_delete", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk, "review_id": review.pk})

def _review_patch_url(journal, issue, article, review):
    return reverse("articles:review_patch", kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk, "review_id": review.pk})


# ──────────────────────────── TestArticleVersionDownloadView ────────────────────────────

@pytest.mark.django_db
class TestArticleVersionDownloadView:
    def test_requires_login(self, client, journal, issue, article, article_version):
        res = client.get(_version_download_url(journal, issue, article, article_version))
        assert res.status_code == 302

    def test_non_member_forbidden(self, client, journal, issue, article, article_version):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other_dl@test.com", password="pass")
        client.force_login(other)
        res = client.get(_version_download_url(journal, issue, article, article_version))
        assert res.status_code == 403

    def test_returns_file(self, client, user, membership, journal, issue, article, article_version):
        client.force_login(user)
        res = client.get(_version_download_url(journal, issue, article, article_version))
        assert res.status_code == 200
        assert res.get("Content-Disposition", "").startswith("attachment")

    def test_archived_article_still_downloadable(self, client, user, membership, journal, issue, article, article_version):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.get(_version_download_url(journal, issue, article, article_version))
        assert res.status_code == 200

    def test_wrong_article_returns_404(self, client, user, membership, journal, issue, article, article_version):
        from apps.articles.models import Article
        other_article = Article.objects.create(issue=issue, title="Autre")
        client.force_login(user)
        url = reverse("articles:version_download", kwargs={
            "slug": journal.slug, "issue_id": issue.pk,
            "article_id": other_article.pk, "version_id": article_version.pk,
        })
        res = client.get(url)
        assert res.status_code == 404


# ──────────────────────────── TestReviewRequestCreateView ────────────────────────────

@pytest.mark.django_db
class TestReviewRequestCreateView:
    def _post(self, client, journal, issue, article, version, contact, deadline=None):
        if deadline is None:
            deadline = (datetime.date.today() + datetime.timedelta(days=28)).isoformat()
        return client.post(
            _review_create_url(journal, issue, article),
            {
                "reviewer_id": contact.pk,
                "reviewer_name": contact.full_name,
                "article_version": version.pk,
                "deadline": deadline,
            },
        )

    def test_requires_login(self, client, journal, issue, article, article_version, contact):
        res = self._post(client, journal, issue, article, article_version, contact)
        assert res.status_code == 302

    def test_creates_review_request(self, client, user, membership, journal, issue, article, article_version, contact):
        client.force_login(user)
        res = self._post(client, journal, issue, article, article_version, contact)
        assert res.status_code == 200
        assert ReviewRequest.objects.filter(article=article).count() == 1

    def test_snapshot_set_from_contact(self, client, user, membership, journal, issue, article, article_version, contact):
        client.force_login(user)
        self._post(client, journal, issue, article, article_version, contact)
        rr = ReviewRequest.objects.get(article=article)
        assert rr.reviewer_name_snapshot == contact.full_name

    def test_creates_audit_note(self, client, user, membership, journal, issue, article, article_version, contact):
        client.force_login(user)
        self._post(client, journal, issue, article, article_version, contact)
        assert InternalNote.objects.filter(article=article, is_automatic=True).exists()

    def test_no_version_returns_400(self, client, user, membership, journal, issue, article, contact):
        client.force_login(user)
        res = client.post(
            _review_create_url(journal, issue, article),
            {"reviewer_id": contact.pk, "reviewer_name": contact.full_name, "article_version": 9999, "deadline": "2030-01-01"},
        )
        assert res.status_code == 400

    def test_reviewer_other_journal_returns_400(self, client, user, membership, journal, issue, article, article_version):
        from apps.journals.models import Journal
        other_journal = Journal.objects.create(name="Autre", slug="autre-rv")
        other_contact = Contact.objects.create(journal=other_journal, first_name="X", last_name="Y")
        client.force_login(user)
        res = client.post(
            _review_create_url(journal, issue, article),
            {"reviewer_id": other_contact.pk, "article_version": article_version.pk, "deadline": "2030-01-01"},
        )
        assert res.status_code == 400

    def test_archived_article_returns_403(self, client, user, membership, journal, issue, article, article_version, contact):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = self._post(client, journal, issue, article, article_version, contact)
        assert res.status_code == 403

    def test_past_deadline_accepted(self, client, user, membership, journal, issue, article, article_version, contact):
        client.force_login(user)
        res = self._post(client, journal, issue, article, article_version, contact, deadline="2020-01-01")
        assert res.status_code == 200

    def test_response_contains_review_item_html(self, client, user, membership, journal, issue, article, article_version, contact):
        client.force_login(user)
        res = self._post(client, journal, issue, article, article_version, contact)
        assert b"review-card" in res.content


# ──────────────────────────── TestReviewRequestReceiveView ────────────────────────────

@pytest.mark.django_db
class TestReviewRequestReceiveView:
    def _post(self, client, journal, issue, article, review, verdict="favorable", file=None):
        data = {"verdict": verdict}
        if file:
            data["received_file"] = file
        return client.post(_review_receive_url(journal, issue, article, review), data)

    def test_requires_login(self, client, journal, issue, article, review_request):
        res = self._post(client, journal, issue, article, review_request)
        assert res.status_code == 302

    def test_marks_review_received(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert res.status_code == 200
        assert ReviewRequest.objects.get(pk=review_request.pk).state == ReviewRequest.State.RECEIVED

    def test_sets_received_at(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        self._post(client, journal, issue, article, review_request)
        assert ReviewRequest.objects.get(pk=review_request.pk).received_at is not None

    def test_verdict_saved(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        self._post(client, journal, issue, article, review_request, verdict="unfavorable")
        assert ReviewRequest.objects.get(pk=review_request.pk).verdict == "unfavorable"

    def test_creates_audit_note(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        self._post(client, journal, issue, article, review_request)
        assert InternalNote.objects.filter(article=article, is_automatic=True).exists()

    def test_without_file_ok(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert res.status_code == 200

    def test_with_file_saved(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        file = ContentFile(b"annotated", name="review.pdf")
        res = self._post(client, journal, issue, article, review_request, file=file)
        assert res.status_code == 200
        assert ReviewRequest.objects.get(pk=review_request.pk).received_file

    def test_already_received_returns_400(self, client, user, membership, journal, issue, article, review_request):
        ReviewRequest.objects.filter(pk=review_request.pk).update(state=ReviewRequest.State.RECEIVED)
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert res.status_code == 400

    def test_archived_article_returns_403(self, client, user, membership, journal, issue, article, review_request):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert res.status_code == 403

    def test_response_contains_oob_received_item(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert b"reviews-received-list" in res.content

    def test_response_contains_oob_counter(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = self._post(client, journal, issue, article, review_request)
        assert b"article-header-counters" in res.content


# ──────────────────────────── TestReviewRequestDeleteView ────────────────────────────

@pytest.mark.django_db
class TestReviewRequestDeleteView:
    def test_requires_login(self, client, journal, issue, article, review_request):
        res = client.post(_review_delete_url(journal, issue, article, review_request))
        assert res.status_code == 302

    def test_soft_deletes_expected_review(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = client.post(_review_delete_url(journal, issue, article, review_request))
        assert res.status_code == 200
        assert not ReviewRequest.objects.filter(pk=review_request.pk).exists()

    def test_review_still_in_all_objects(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        client.post(_review_delete_url(journal, issue, article, review_request))
        assert ReviewRequest.all_objects.filter(pk=review_request.pk).exists()

    def test_creates_audit_note(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        client.post(_review_delete_url(journal, issue, article, review_request))
        assert InternalNote.objects.filter(article=article, is_automatic=True, content__icontains="annul").exists()

    def test_received_review_cannot_be_deleted(self, client, user, membership, journal, issue, article, review_request):
        ReviewRequest.objects.filter(pk=review_request.pk).update(state=ReviewRequest.State.RECEIVED)
        client.force_login(user)
        res = client.post(_review_delete_url(journal, issue, article, review_request))
        assert res.status_code == 400

    def test_archived_article_returns_403(self, client, user, membership, journal, issue, article, review_request):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.post(_review_delete_url(journal, issue, article, review_request))
        assert res.status_code == 403

    def test_snapshot_preserved_after_contact_deletion(self, client, user, membership, journal, issue, article, review_request):
        from apps.contacts.models import Contact
        from apps.reviews.models import ReviewRequest as RR
        reviewer = Contact.objects.create(
            journal=journal,
            first_name="Marie",
            last_name="Curie",
            usual_roles=[Contact.Role.EXTERNAL_REVIEWER],
        )
        review_request.reviewer = reviewer
        review_request.reviewer_name_snapshot = reviewer.full_name
        review_request.save()
        snapshot = reviewer.full_name
        Article.objects.filter(author=reviewer).update(author=None)
        reviewer.hard_delete()
        rr = RR.objects.get(pk=review_request.pk)
        assert rr.reviewer_name_snapshot == snapshot
        assert rr.reviewer is None


# ──────────────────────────── TestReviewRequestPatchView ────────────────────────────

@pytest.mark.django_db
class TestReviewRequestPatchView:
    def _patch(self, client, journal, issue, article, review, field, value):
        import json
        return client.post(
            _review_patch_url(journal, issue, article, review),
            data=json.dumps({"field": field, "value": value}),
            content_type="application/json",
        )

    def test_patch_internal_notes_on_received(self, client, user, membership, journal, issue, article, review_request):
        ReviewRequest.objects.filter(pk=review_request.pk).update(
            state=ReviewRequest.State.RECEIVED, verdict="favorable"
        )
        review_request.refresh_from_db()
        client.force_login(user)
        res = self._patch(client, journal, issue, article, review_request, "internal_notes", "Note test")
        assert res.status_code == 200
        assert ReviewRequest.objects.get(pk=review_request.pk).internal_notes == "Note test"

    def test_patch_deadline_on_expected(self, client, user, membership, journal, issue, article, review_request):
        client.force_login(user)
        res = self._patch(client, journal, issue, article, review_request, "deadline", "2030-06-01")
        assert res.status_code == 200
        assert str(ReviewRequest.objects.get(pk=review_request.pk).deadline) == "2030-06-01"

    def test_patch_deadline_on_received_returns_400(self, client, user, membership, journal, issue, article, review_request):
        ReviewRequest.objects.filter(pk=review_request.pk).update(
            state=ReviewRequest.State.RECEIVED, verdict="favorable"
        )
        review_request.refresh_from_db()
        client.force_login(user)
        res = self._patch(client, journal, issue, article, review_request, "deadline", "2030-06-01")
        assert res.status_code == 400

    def test_patch_verdict_on_received(self, client, user, membership, journal, issue, article, review_request):
        ReviewRequest.objects.filter(pk=review_request.pk).update(
            state=ReviewRequest.State.RECEIVED, verdict="favorable"
        )
        review_request.refresh_from_db()
        client.force_login(user)
        res = self._patch(client, journal, issue, article, review_request, "verdict", "unfavorable")
        assert res.status_code == 200
        assert ReviewRequest.objects.get(pk=review_request.pk).verdict == "unfavorable"

    def test_patch_archived_returns_403(self, client, user, membership, journal, issue, article, review_request):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = self._patch(client, journal, issue, article, review_request, "internal_notes", "X")
        assert res.status_code == 403


# ------------------------------------------------------------------ #
# ArticleCreateView                                                   #
# ------------------------------------------------------------------ #


def _article_create_url(journal, issue):
    return reverse(
        "articles:create",
        kwargs={"slug": journal.slug, "issue_id": issue.pk},
    )


@pytest.mark.django_db
class TestArticleCreateView:
    def test_unauthenticated_redirects(self, client, journal, issue):
        response = client.get(_article_create_url(journal, issue))
        assert response.status_code == 302

    def test_member_can_get_form(self, client, user, membership, journal, issue):
        client.force_login(user)
        response = client.get(_article_create_url(journal, issue))
        assert response.status_code == 200
        assert "form" in response.context

    def test_valid_post_creates_article_in_pending_without_file(self, client, user, membership, journal, issue):
        client.force_login(user)
        response = client.post(_article_create_url(journal, issue), {
            "title": "Mon article",
            "article_type": Article.Type.ARTICLE,
        })
        assert response.status_code == 302
        a = Article.objects.get(issue=issue, title="Mon article")
        assert a.state == Article.State.PENDING
        assert response["Location"] == reverse(
            "issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk}
        )

    def test_valid_post_creates_article_in_received_with_file(self, client, user, membership, journal, issue):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client.force_login(user)
        f = SimpleUploadedFile("article.pdf", b"pdf content", content_type="application/pdf")
        response = client.post(_article_create_url(journal, issue), {
            "title": "Article avec fichier",
            "article_type": Article.Type.ARTICLE,
            "file": f,
        })
        assert response.status_code == 302
        a = Article.objects.get(issue=issue, title="Article avec fichier")
        assert a.state == Article.State.RECEIVED
        assert a.versions.count() == 1

    def test_valid_post_saves_abstract(self, client, user, membership, journal, issue):
        client.force_login(user)
        client.post(_article_create_url(journal, issue), {
            "title": "Avec résumé",
            "article_type": Article.Type.ARTICLE,
            "abstract": "Cet article traite de…",
        })
        a = Article.objects.get(issue=issue, title="Avec résumé")
        assert a.abstract == "Cet article traite de…"

    def test_article_belongs_to_issue(self, client, user, membership, journal, issue):
        client.force_login(user)
        client.post(_article_create_url(journal, issue), {
            "title": "Appartenance",
            "article_type": Article.Type.ARTICLE,
        })
        a = Article.objects.get(title="Appartenance")
        assert a.issue == issue

    def test_archived_issue_returns_403(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        response = client.get(_article_create_url(journal, issue))
        assert response.status_code == 403

    def test_file_upload_creates_version(self, client, user, membership, journal, issue):
        from django.core.files.base import ContentFile
        from apps.articles.models import ArticleVersion

        client.force_login(user)
        client.post(_article_create_url(journal, issue), {
            "title": "Avec fichier",
            "article_type": Article.Type.ARTICLE,
            "file": ContentFile(b"%PDF content", name="article.pdf"),
        })
        a = Article.objects.get(title="Avec fichier")
        assert ArticleVersion.objects.filter(article=a).count() == 1

    def test_no_file_creates_no_version(self, client, user, membership, journal, issue):
        from apps.articles.models import ArticleVersion

        client.force_login(user)
        client.post(_article_create_url(journal, issue), {
            "title": "Sans fichier",
            "article_type": Article.Type.ARTICLE,
        })
        a = Article.objects.get(title="Sans fichier")
        assert ArticleVersion.objects.filter(article=a).count() == 0

    def test_invalid_post_rerenders_form(self, client, user, membership, journal, issue):
        client.force_login(user)
        response = client.post(_article_create_url(journal, issue), {"title": ""})
        assert response.status_code == 200
        assert response.context["form"].errors


# ------------------------------------------------------------------ #
# ArticleCreateFromJournalView                                        #
# ------------------------------------------------------------------ #


def _article_create_from_journal_url(journal):
    return reverse("article_create_from_journal", kwargs={"slug": journal.slug})


@pytest.mark.django_db
class TestArticleCreateFromJournalView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_article_create_from_journal_url(journal))
        assert response.status_code == 302

    def test_no_active_issues_redirects_to_issue_create(self, client, user, membership, journal):
        client.force_login(user)
        response = client.get(_article_create_from_journal_url(journal))
        assert response.status_code == 302
        assert reverse("issues:create", kwargs={"slug": journal.slug}) in response["Location"]

    def test_with_active_issue_shows_form(self, client, user, membership, journal, issue):
        client.force_login(user)
        response = client.get(_article_create_from_journal_url(journal))
        assert response.status_code == 200
        assert "form" in response.context

    def test_valid_post_creates_article_linked_to_issue(self, client, user, membership, journal, issue):
        client.force_login(user)
        response = client.post(_article_create_from_journal_url(journal), {
            "issue": issue.pk,
            "title": "Article depuis dashboard",
            "article_type": Article.Type.ARTICLE,
        })
        assert response.status_code == 302
        a = Article.objects.get(title="Article depuis dashboard")
        assert a.issue == issue

    def test_archived_issues_not_in_form_choices(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        active = Issue.objects.create(
            journal=journal, number="2", thematic_title="Actif", editor_name="Ed"
        )
        client.force_login(user)
        response = client.get(_article_create_from_journal_url(journal))
        form = response.context["form"]
        pks = [obj.pk for obj in form.fields["issue"].queryset]
        assert issue.pk not in pks
        assert active.pk in pks
