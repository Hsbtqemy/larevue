import pytest
from django.urls import reverse

from apps.articles.models import Article
from apps.contacts.models import Contact
from apps.issues.models import Issue


def _create_url(journal, issue):
    return reverse("articles:create", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _edit_url(journal, issue, article):
    return reverse(
        "articles:edit",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _base_create_data(**overrides):
    data = {"title": "Test Article", "article_type": "article"}
    data.update(overrides)
    return data


def _base_edit_data(**overrides):
    data = {"title": "Test Article", "article_type": "article"}
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestArticleCreateAuthorFreetext:
    def test_create_with_contact_author(self, client, user, membership, issue, contact):
        client.force_login(user)
        response = client.post(_create_url(membership.journal, issue), _base_create_data(
            author_id=str(contact.pk),
            author_name=contact.full_name,
        ))
        assert response.status_code == 302
        article = Article.objects.get(issue=issue, title="Test Article")
        assert article.author == contact
        assert article.author_name_override == ""

    def test_create_with_freetext_author(self, client, user, membership, issue):
        client.force_login(user)
        response = client.post(_create_url(membership.journal, issue), _base_create_data(
            author_id="",
            author_name="Auteur Libre",
        ))
        assert response.status_code == 302
        article = Article.objects.get(issue=issue, title="Test Article")
        assert article.author is None
        assert article.author_name_override == "Auteur Libre"

    def test_create_without_author(self, client, user, membership, issue):
        client.force_login(user)
        response = client.post(_create_url(membership.journal, issue), _base_create_data())
        assert response.status_code == 302
        article = Article.objects.get(issue=issue, title="Test Article")
        assert article.author is None
        assert article.author_name_override == ""

    def test_create_with_invalid_author_id_falls_back_to_freetext(self, client, user, membership, issue):
        client.force_login(user)
        response = client.post(_create_url(membership.journal, issue), _base_create_data(
            author_id="99999",
            author_name="Fallback Name",
        ))
        assert response.status_code == 302
        article = Article.objects.get(issue=issue, title="Test Article")
        assert article.author is None
        assert article.author_name_override == "Fallback Name"

    def test_create_with_other_journal_contact_falls_back(self, client, user, membership, issue, db):
        from apps.journals.models import Journal
        other = Journal.objects.create(name="Autre", slug="autre-freetext")
        other_contact = Contact.objects.create(journal=other, first_name="X", last_name="Y")
        client.force_login(user)
        response = client.post(_create_url(membership.journal, issue), _base_create_data(
            author_id=str(other_contact.pk),
            author_name="X Y",
        ))
        assert response.status_code == 302
        article = Article.objects.get(issue=issue, title="Test Article")
        assert article.author is None
        assert article.author_name_override == "X Y"


@pytest.mark.django_db
class TestArticleEditAuthorFreetext:
    def test_edit_sets_contact_author(self, client, user, membership, journal, issue, article, contact):
        client.force_login(user)
        response = client.post(_edit_url(journal, issue, article), _base_edit_data(
            title=article.title,
            author_id=str(contact.pk),
            author_name=contact.full_name,
        ))
        assert response.status_code == 200
        updated = Article.objects.get(pk=article.pk)
        assert updated.author == contact
        assert updated.author_name_override == ""

    def test_edit_sets_freetext_author(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        response = client.post(_edit_url(journal, issue, article), _base_edit_data(
            title=article.title,
            author_id="",
            author_name="Auteur Manuel",
        ))
        assert response.status_code == 200
        updated = Article.objects.get(pk=article.pk)
        assert updated.author is None
        assert updated.author_name_override == "Auteur Manuel"

    def test_edit_clears_author(self, client, user, membership, journal, issue, article, contact):
        Article.objects.filter(pk=article.pk).update(author=contact)
        client.force_login(user)
        response = client.post(_edit_url(journal, issue, article), _base_edit_data(
            title=article.title,
            author_id="",
            author_name="",
        ))
        assert response.status_code == 200
        updated = Article.objects.get(pk=article.pk)
        assert updated.author is None
        assert updated.author_name_override == ""

    def test_displayed_author_name_uses_override(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        client.post(_edit_url(journal, issue, article), _base_edit_data(
            title=article.title,
            author_id="",
            author_name="Nom Surchargé",
        ))
        updated = Article.objects.get(pk=article.pk)
        assert updated.displayed_author_name == "Nom Surchargé"

    def test_displayed_author_name_uses_contact_when_linked(
        self, client, user, membership, journal, issue, article, contact
    ):
        client.force_login(user)
        client.post(_edit_url(journal, issue, article), _base_edit_data(
            title=article.title,
            author_id=str(contact.pk),
            author_name=contact.full_name,
        ))
        updated = Article.objects.get(pk=article.pk)
        assert updated.displayed_author_name == contact.full_name
