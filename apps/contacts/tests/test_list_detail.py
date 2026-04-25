import json

import pytest
from django.urls import reverse

from apps.articles.models import Article
from apps.contacts.models import Contact


def _list_url(journal):
    return reverse("contacts:list", kwargs={"slug": journal.slug})


def _detail_url(journal, contact):
    return reverse("contacts:detail", kwargs={"slug": journal.slug, "pk": contact.pk})


def _patch_url(journal, contact):
    return reverse("contacts:patch", kwargs={"slug": journal.slug, "pk": contact.pk})


def _edit_url(journal, contact):
    return reverse("contacts:edit", kwargs={"slug": journal.slug, "pk": contact.pk})


def _delete_url(journal, contact):
    return reverse("contacts:delete", kwargs={"slug": journal.slug, "pk": contact.pk})


# ──────────────────────────── ContactListView ────────────────────────────

@pytest.mark.django_db
class TestContactListView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_list_url(journal))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User
        from apps.journals.models import Journal

        j = Journal.objects.create(name="Autre", slug="autre-contact-list")
        u = User.objects.create_user(email="x2@x.com", password="pass")
        client.force_login(u)
        response = client.get(_list_url(j))
        assert response.status_code == 403

    def test_member_gets_200(self, client, user, membership):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert response.status_code == 200

    def test_contacts_in_context(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert contact in response.context["contacts"]

    def test_contacts_from_other_journal_excluded(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-excl")
        Contact.objects.create(journal=other, first_name="X", last_name="Y")
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        assert all(c.journal == membership.journal for c in response.context["contacts"])

    def test_annotated_counts_present(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        c = next(c for c in response.context["contacts"] if c.pk == contact.pk)
        assert hasattr(c, "article_count")
        assert hasattr(c, "review_count")

    def test_article_count_reflects_authored(self, client, user, membership, contact, article):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        c = next(c for c in response.context["contacts"] if c.pk == contact.pk)
        assert c.article_count == 1

    def test_review_count_reflects_reviews(self, client, user, membership, contact, review_request):
        client.force_login(user)
        response = client.get(_list_url(membership.journal))
        c = next(c for c in response.context["contacts"] if c.pk == contact.pk)
        assert c.review_count == 1


# ──────────────────────────── ContactDetailView ────────────────────────────

@pytest.mark.django_db
class TestContactDetailView:
    def test_unauthenticated_redirects(self, client, journal, contact):
        response = client.get(_detail_url(journal, contact))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_member_gets_200(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_detail_url(membership.journal, contact))
        assert response.status_code == 200

    def test_contact_in_context(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_detail_url(membership.journal, contact))
        assert response.context["contact"] == contact

    def test_contact_from_other_journal_returns_404(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-detail")
        other_contact = Contact.objects.create(journal=other, first_name="A", last_name="B")
        client.force_login(user)
        response = client.get(_detail_url(membership.journal, other_contact))
        assert response.status_code == 404

    def test_articles_in_context(self, client, user, membership, contact, article):
        client.force_login(user)
        response = client.get(_detail_url(membership.journal, contact))
        assert article in response.context["articles"]

    def test_reviews_in_context(self, client, user, membership, contact, review_request):
        client.force_login(user)
        response = client.get(_detail_url(membership.journal, contact))
        assert review_request in response.context["reviews"]


# ──────────────────────────── ContactPatchView ────────────────────────────

@pytest.mark.django_db
class TestContactPatchView:
    def _patch(self, client, journal, contact, field, value):
        return client.post(
            _patch_url(journal, contact),
            data=json.dumps({"field": field, "value": value}),
            content_type="application/json",
        )

    def test_unauthenticated_redirects(self, client, journal, contact):
        response = self._patch(client, journal, contact, "first_name", "Test")
        assert response.status_code == 302

    def test_valid_patch_updates_field(self, client, user, membership, contact):
        client.force_login(user)
        response = self._patch(client, membership.journal, contact, "first_name", "Marie")
        assert response.status_code == 200
        contact.refresh_from_db()
        assert contact.first_name == "Marie"

    def test_patch_affiliation(self, client, user, membership, contact):
        client.force_login(user)
        response = self._patch(client, membership.journal, contact, "affiliation", "CNRS")
        assert response.status_code == 200
        contact.refresh_from_db()
        assert contact.affiliation == "CNRS"

    def test_disallowed_field_returns_400(self, client, user, membership, contact):
        client.force_login(user)
        response = self._patch(client, membership.journal, contact, "usual_roles", "author")
        assert response.status_code == 400

    def test_contact_from_other_journal_returns_404(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-patch")
        other_contact = Contact.objects.create(journal=other, first_name="A", last_name="B")
        client.force_login(user)
        response = self._patch(client, membership.journal, other_contact, "first_name", "X")
        assert response.status_code == 404


# ──────────────────────────── ContactEditView ────────────────────────────

@pytest.mark.django_db
class TestContactEditView:
    def _post(self, client, journal, contact, data):
        return client.post(_edit_url(journal, contact), data)

    def test_valid_edit_updates_contact(self, client, user, membership, contact):
        client.force_login(user)
        response = self._post(client, membership.journal, contact, {
            "first_name": "Nouvelle",
            "last_name": "Valeur",
            "email": "new@example.com",
            "affiliation": "Univ",
            "usual_roles": [Contact.Role.AUTHOR],
            "notes": "",
        })
        assert response.status_code == 200
        data = response.json()
        assert "redirect_url" in data
        contact.refresh_from_db()
        assert contact.first_name == "Nouvelle"
        assert Contact.Role.AUTHOR in contact.usual_roles

    def test_invalid_edit_returns_400(self, client, user, membership, contact):
        client.force_login(user)
        response = self._post(client, membership.journal, contact, {
            "first_name": "",
            "last_name": "",
        })
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data

    def test_unauthenticated_redirects(self, client, journal, contact):
        response = self._post(client, journal, contact, {})
        assert response.status_code == 302


# ──────────────────────────── ContactDeleteView ────────────────────────────

@pytest.mark.django_db
class TestContactDeleteView:
    def _delete(self, client, journal, contact):
        return client.delete(_delete_url(journal, contact))

    def test_unauthenticated_redirects(self, client, journal, contact):
        response = self._delete(client, journal, contact)
        assert response.status_code == 302

    def test_deletes_contact(self, client, user, membership, contact):
        client.force_login(user)
        response = self._delete(client, membership.journal, contact)
        assert response.status_code == 200
        assert not Contact.objects.filter(pk=contact.pk).exists()

    def test_redirects_to_list(self, client, user, membership, contact):
        client.force_login(user)
        response = self._delete(client, membership.journal, contact)
        data = response.json()
        assert data["redirect_url"] == reverse(
            "contacts:list", kwargs={"slug": membership.journal.slug}
        )

    def test_prefills_author_name_override(self, client, user, membership, contact, article):
        client.force_login(user)
        assert article.author == contact
        assert article.author_name_override == ""
        full_name = contact.full_name
        self._delete(client, membership.journal, contact)
        refreshed = Article.objects.get(pk=article.pk)
        assert refreshed.author_name_override == full_name

    def test_does_not_overwrite_existing_override(self, client, user, membership, contact, article):
        Article.objects.filter(pk=article.pk).update(author_name_override="Override existant")
        client.force_login(user)
        self._delete(client, membership.journal, contact)
        refreshed = Article.objects.get(pk=article.pk)
        assert refreshed.author_name_override == "Override existant"

    def test_contact_from_other_journal_returns_404(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-delete")
        other_contact = Contact.objects.create(journal=other, first_name="A", last_name="B")
        client.force_login(user)
        response = self._delete(client, membership.journal, other_contact)
        assert response.status_code == 404
