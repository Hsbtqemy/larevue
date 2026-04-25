import json

import pytest
from django.urls import reverse

from apps.articles.models import InternalNote
from apps.issues.models import Issue


def _create_url(journal):
    return reverse("issues:create", kwargs={"slug": journal.slug})


def _list_url(journal, tab=None):
    url = reverse("issues:list", kwargs={"slug": journal.slug})
    if tab:
        url += f"?tab={tab}"
    return url


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

    def test_primary_transitions_for_under_review(self, client, user, membership, journal, issue):
        client.force_login(user)
        primary = client.get(_detail_url(journal, issue)).context["transitions"]["primary"]
        names = {t["name"] for t in primary}
        assert "accept" in names
        assert "refuse" in names

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

    def test_patch_deadline_articles(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_articles", "value": "2025-06-15"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_articles.isoformat() == "2025-06-15"

    def test_patch_deadline_reviews(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_reviews", "value": "2025-07-01"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_reviews.isoformat() == "2025-07-01"

    def test_patch_deadline_v2(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_v2", "value": "2025-08-10"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_v2.isoformat() == "2025-08-10"

    def test_patch_deadline_final_check(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_final_check", "value": "2025-09-05"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_final_check.isoformat() == "2025-09-05"

    def test_patch_deadline_sent_to_publisher(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_sent_to_publisher", "value": "2025-10-01"})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_sent_to_publisher.isoformat() == "2025-10-01"

    def test_patch_deadline_creates_audit_note(self, client, user, membership, journal, issue):
        client.force_login(user)
        _json_post(client, _patch_url(journal, issue), {"field": "deadline_articles", "value": "2025-06-15"})
        assert InternalNote.objects.filter(issue=issue, is_automatic=True).exists()

    def test_patch_deadline_clear_with_empty_value(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(deadline_articles="2025-06-15")
        client.force_login(user)
        res = _json_post(client, _patch_url(journal, issue), {"field": "deadline_articles", "value": ""})
        assert res.status_code == 200
        assert Issue.objects.get(pk=issue.pk).deadline_articles is None

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


@pytest.mark.django_db
class TestIssueDetailTimeline:
    def test_timeline_in_context(self, client, user, membership, journal, issue):
        client.force_login(user)
        ctx = client.get(_detail_url(journal, issue)).context
        assert "timeline" in ctx

    def test_timeline_has_seven_milestones(self, client, user, membership, journal, issue):
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        assert len(timeline) == 7

    def test_timeline_current_milestone_for_under_review(self, client, user, membership, journal, issue):
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        current = next(m for m in timeline if m["is_current"])
        assert current["state"] == Issue.State.UNDER_REVIEW

    def test_timeline_no_done_milestones_for_initial_state(self, client, user, membership, journal, issue):
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        assert not any(m["is_done"] for m in timeline)

    def test_timeline_done_milestones_after_accept(self, client, user, membership, journal, issue):
        issue.accept()
        issue.save()
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        done = [m for m in timeline if m["is_done"]]
        assert len(done) == 1
        assert done[0]["state"] == Issue.State.UNDER_REVIEW

    def test_timeline_deadline_is_late_when_past(self, client, user, membership, journal, issue):
        import datetime
        past = datetime.date.today() - datetime.timedelta(days=3)
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.ACCEPTED, deadline_articles=past)
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        in_review_ms = next(m for m in timeline if m["state"] == Issue.State.IN_REVIEW)
        assert in_review_ms["is_late"] is True

    def test_timeline_position_pct_first_and_last(self, client, user, membership, journal, issue):
        client.force_login(user)
        timeline = client.get(_detail_url(journal, issue)).context["timeline"]
        assert timeline[0]["position_pct"] == 0
        assert timeline[-1]["position_pct"] == 100


class _FakeMigrationContext:
    """Minimal stubs so migration functions can call apps.get_model()."""
    class apps:
        @staticmethod
        def get_model(app, model):
            from django.apps import apps as real_apps
            return real_apps.get_model(app, model)

    class schema_editor:
        pass


def _migration_0002():
    import importlib
    return importlib.import_module("apps.issues.migrations.0002_issue_state_v2_deadlines")


@pytest.mark.django_db
class TestMigrationFunctions:
    def test_forward_maps_in_production_to_accepted(self, issue):
        forward_migrate_states = _migration_0002().forward_migrate_states
        Issue.objects.filter(pk=issue.pk).update(state="in_production")
        forward_migrate_states(_FakeMigrationContext.apps, _FakeMigrationContext.schema_editor)
        assert Issue.objects.get(pk=issue.pk).state == "accepted"

    def test_forward_leaves_other_states_unchanged(self, issue):
        forward_migrate_states = _migration_0002().forward_migrate_states
        forward_migrate_states(_FakeMigrationContext.apps, _FakeMigrationContext.schema_editor)
        assert Issue.objects.get(pk=issue.pk).state == Issue.State.UNDER_REVIEW

    def test_backward_maps_new_states_to_in_production(self, journal):
        backward_migrate_states = _migration_0002().backward_migrate_states
        pks = []
        for state in ["in_review", "in_revision", "final_check"]:
            i = Issue.objects.create(
                journal=journal, number=f"BW-{state}",
                thematic_title=f"Test {state}", editor_name="Test",
            )
            Issue.objects.filter(pk=i.pk).update(state=state)
            pks.append(i.pk)

        backward_migrate_states(_FakeMigrationContext.apps, _FakeMigrationContext.schema_editor)
        for pk in pks:
            assert Issue.objects.get(pk=pk).state == "in_production"


# ------------------------------------------------------------------ #
# IssueCreateView                                                     #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestIssueCreateView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_create_url(journal))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User
        from apps.journals.models import Journal

        j = Journal.objects.create(name="Autre", slug="autre")
        u = User.objects.create_user(email="x@x.com", password="pass")
        client.force_login(u)
        response = client.get(_create_url(j))
        assert response.status_code == 403

    def test_member_can_get_form(self, client, user, membership):
        client.force_login(user)
        response = client.get(_create_url(membership.journal))
        assert response.status_code == 200
        assert "form" in response.context

    def test_valid_post_creates_issue(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "number": "42",
            "thematic_title": "Titre du numéro",
            "description": "",
            "editor_name": "Éditeur",
            "planned_publication_date": "",
            "deadline_articles": "",
        })
        assert response.status_code == 302
        new_issue = Issue.objects.get(journal=membership.journal, number="42")
        assert new_issue.thematic_title == "Titre du numéro"
        assert new_issue.state == Issue.State.UNDER_REVIEW
        assert response["Location"] == reverse(
            "issues:detail", kwargs={"slug": membership.journal.slug, "issue_id": new_issue.pk}
        )

    def test_invalid_post_rerenders_form(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "number": "",
            "thematic_title": "",
            "editor_name": "",
        })
        assert response.status_code == 200
        assert response.context["form"].errors

    def test_issue_belongs_to_journal(self, client, user, membership):
        client.force_login(user)
        client.post(_create_url(membership.journal), {
            "number": "99",
            "thematic_title": "Test appartenance",
            "description": "",
            "editor_name": "Ed",
            "planned_publication_date": "",
            "deadline_articles": "",
        })
        issue = Issue.objects.get(number="99")
        assert issue.journal == membership.journal


# ------------------------------------------------------------------ #
# IssueListView                                                       #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
class TestIssueListView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_list_url(journal))
        assert response.status_code == 302

    def test_member_sees_active_tab_by_default(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert response.status_code == 200
        assert response.context["tab"] != "archived"
        assert issue in list(response.context["active_issues"])

    def test_archived_tab_shows_archived_issues(self, client, user, membership, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        response = client.get(_list_url(membership.journal, tab="archived"))
        assert response.status_code == 200
        assert response.context["tab"] == "archived"
        assert issue.pk in [i.pk for i in response.context["archived_issues"]]

    def test_active_issue_not_in_archived_tab(self, client, user, membership, issue):
        client.force_login(user)
        response = client.get(_list_url(membership.journal, tab="archived"))
        assert issue.pk not in [i.pk for i in response.context["archived_issues"]]

    def test_counts_in_context(self, client, user, membership, issue, db):
        from apps.journals.models import Journal

        Issue.objects.create(
            journal=membership.journal, number="2",
            thematic_title="Deuxième", editor_name="Ed",
        )
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert response.context["active_count"] == 1
        assert response.context["archived_count"] == 1

    def test_other_journal_issues_not_shown(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre")
        Issue.objects.create(journal=other, number="X", thematic_title="Autre", editor_name="Ed")
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert all(i.journal_id == membership.journal.pk for i in response.context["active_issues"])
