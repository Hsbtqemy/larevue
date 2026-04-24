import json

import pytest
from django.urls import reverse

from apps.articles.models import InternalNote
from apps.issues.models import Issue


def _detail_url(journal, issue):
    return reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _patch_url(journal, issue):
    return reverse("issues:patch", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _edit_url(journal, issue):
    return reverse("issues:edit", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _delete_url(journal, issue):
    return reverse("issues:delete", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _json_post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
class TestIssueDetailView:
    def test_requires_login(self, client, journal, issue):
        res = client.get(_detail_url(journal, issue))
        assert res.status_code == 302

    def test_non_member_forbidden(self, client, journal, issue):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.get(_detail_url(journal, issue))
        assert res.status_code == 403

    def test_issue_from_other_journal_is_404(self, client, user, membership, journal, issue):
        from apps.journals.models import Journal, Membership
        other = Journal.objects.create(name="Autre revue", slug="autre-revue")
        Membership.objects.create(user=user, journal=other)
        client.force_login(user)
        url = reverse("issues:detail", kwargs={"slug": "autre-revue", "issue_id": issue.pk})
        res = client.get(url)
        assert res.status_code == 404

    def test_ok(self, client, user, membership, journal, issue):
        client.force_login(user)
        assert client.get(_detail_url(journal, issue)).status_code == 200

    def test_is_editable_true_for_active_issue(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert ctx["is_editable"] is True

    def test_is_editable_false_for_published_issue(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert ctx["is_editable"] is False

    def test_is_editable_false_for_refused_issue(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.REFUSED)
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert ctx["is_editable"] is False

    def test_primary_transition_accept_for_under_review(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert ctx["transitions"]["primary"]["name"] == "accept"

    def test_articles_in_context(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert len(ctx["articles"]) == 1

    def test_article_annotations_no_versions_or_reviews(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        a = client.get(_detail_url(journal, issue)).context["articles"][0]
        assert a.latest_version is None
        assert a.reviews_received == 0
        assert a.reviews_total == 0

    def test_member_names_includes_editor(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert issue.editor_name in ctx["member_names"]

    def test_articles_ordered_by_order(self, client, user, membership, journal, issue):
        from apps.articles.models import Article
        Article.objects.create(issue=issue, title="Z", order=2)
        Article.objects.create(issue=issue, title="A", order=1)
        client.force_login(user)
        articles = client.get(_detail_url(journal, issue)).context["articles"]
        assert articles[0].order <= articles[1].order


@pytest.mark.django_db
class TestIssuePatchView:
    def test_requires_login(self, client, journal, issue):
        res = _json_post(client, _patch_url(journal, issue), {"field": "number", "value": "99"})
        assert res.status_code == 302

    def test_patch_allowed_field(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "number", "value": "99"})
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert Issue.objects.get(pk=issue.pk).number == "99"

    def test_patch_creates_audit_note(self, client, user, membership, journal, issue):
        client.force_login(user)
        _json_post(client, _patch_url(journal, issue), {"field": "thematic_title", "value": "Nouveau"})
        note = InternalNote.objects.filter(issue=issue, is_automatic=True).last()
        assert note is not None
        assert "Nouveau" in note.content

    def test_patch_description(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "description", "value": "Texte"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).description == "Texte"

    def test_patch_forbidden_field(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "state", "value": "published"})
        assert res.status_code == 400

    def test_patch_non_member_forbidden(self, client, journal, issue):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other2@test.com", password="pass")
        client.force_login(other)
        res = _json_post(client, _patch_url(journal, issue), {"field": "number", "value": "2"})
        assert res.status_code == 403

    def test_patch_archived_issue_forbidden(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "number", "value": "2"})
        assert res.status_code == 403

    def test_patch_invalid_value_too_long(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(
            client, _patch_url(journal, issue),
            {"field": "thematic_title", "value": "x" * 301},
        )
        assert res.status_code == 400
        assert "error" in res.json()

    def test_patch_malformed_json(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = client.post(
            _patch_url(journal, issue),
            data="not-json",
            content_type="application/json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestIssueEditView:
    def _form_data(self, issue, **overrides):
        data = {
            "number": issue.number,
            "thematic_title": issue.thematic_title,
            "editor_name": issue.editor_name,
            "planned_publication_date": "",
            "description": issue.description,
        }
        data.update(overrides)
        return data

    def test_valid_edit_saves_and_returns_redirect_url(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = client.post(_edit_url(journal, issue), self._form_data(issue, thematic_title="Nouveau"))
        assert res.status_code == 200
        data = res.json()
        assert "redirect_url" in data
        assert Issue.objects.get(pk=issue.pk).thematic_title == "Nouveau"

    def test_invalid_edit_returns_errors(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = client.post(_edit_url(journal, issue), self._form_data(issue, number=""))
        assert res.status_code == 400
        assert "number" in res.json()["errors"]

    def test_edit_archived_issue_forbidden(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.REFUSED)
        client.force_login(user)
        res = client.post(_edit_url(journal, issue), self._form_data(issue))
        assert res.status_code == 403

    def test_requires_login(self, client, journal, issue):
        res = client.post(_edit_url(journal, issue), {})
        assert res.status_code == 302


@pytest.mark.django_db
class TestIssueDeleteView:
    def test_delete_soft_deletes_issue(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = client.delete(_delete_url(journal, issue))
        assert res.status_code == 200
        assert "redirect_url" in res.json()
        from apps.issues.models import Issue
        assert not Issue.objects.filter(pk=issue.pk).exists()

    def test_deleted_issue_still_in_all_objects(self, client, user, membership, journal, issue):
        client.force_login(user)
        client.delete(_delete_url(journal, issue))
        assert Issue.all_objects.filter(pk=issue.pk).exists()

    def test_redirect_url_points_to_dashboard(self, client, user, membership, journal, issue):
        client.force_login(user)
        data = client.delete(_delete_url(journal, issue)).json()
        expected = reverse("journal_dashboard", kwargs={"slug": journal.slug})
        assert data["redirect_url"] == expected

    def test_non_member_forbidden(self, client, journal, issue):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other3@test.com", password="pass")
        client.force_login(other)
        res = client.delete(_delete_url(journal, issue))
        assert res.status_code == 403

    def test_requires_login(self, client, journal, issue):
        res = client.delete(_delete_url(journal, issue))
        assert res.status_code == 302
