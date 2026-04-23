import pytest
from django.urls import reverse

from apps.articles.models import Article, InternalNote
from apps.contacts.models import Contact
from apps.issues.models import Issue


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
        for key in ("article", "issue", "journal", "internal_notes", "author_options", "is_archived"):
            assert key in ctx

    def test_author_options_filtered_by_journal(self, client, user, membership, journal, issue, article):
        from apps.journals.models import Journal
        other_journal = Journal.objects.create(name="Autre", slug="autre2")
        Contact.objects.create(journal=other_journal, first_name="Étranger", last_name="X")
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue, article)).context
        names = [name for _, name in ctx["author_options"]]
        assert "Étranger X" not in names

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
            "author": article.author_id or "",
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
