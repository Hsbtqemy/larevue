import pytest
from django.urls import reverse

from apps.contacts.models import Contact


def _search_url(journal, **params):
    url = reverse("contacts:search", kwargs={"slug": journal.slug})
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    return url


@pytest.mark.django_db
class TestContactSearchAPIView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_search_url(journal, q="test"))
        assert response.status_code == 302

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User
        from apps.journals.models import Journal

        j = Journal.objects.create(name="Autre", slug="autre-search")
        u = User.objects.create_user(email="s@x.com", password="pass")
        client.force_login(u)
        response = client.get(_search_url(j, q="test"))
        assert response.status_code == 403

    def test_empty_query_returns_all(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal))
        assert response.status_code == 200
        data = response.json()
        assert any(r["id"] == contact.pk for r in data["results"])

    def test_match_by_last_name(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Dupont"))
        data = response.json()
        assert any(r["id"] == contact.pk for r in data["results"])

    def test_match_by_first_name(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Jean"))
        data = response.json()
        assert any(r["id"] == contact.pk for r in data["results"])

    def test_match_by_affiliation(self, client, user, membership, db):
        c = Contact.objects.create(
            journal=membership.journal,
            first_name="Test",
            last_name="Aff",
            affiliation="Université Paris",
        )
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Paris"))
        data = response.json()
        assert any(r["id"] == c.pk for r in data["results"])

    def test_case_insensitive(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="dupont"))
        data = response.json()
        assert any(r["id"] == contact.pk for r in data["results"])

    def test_no_match_returns_empty(self, client, user, membership):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="zzznomatch"))
        data = response.json()
        assert data["results"] == []

    def test_other_journal_contacts_excluded(self, client, user, membership, db):
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-search-excl")
        Contact.objects.create(journal=other, first_name="Visible", last_name="Other")
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Visible"))
        data = response.json()
        assert data["results"] == []

    def test_role_filter_includes_match(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, role=Contact.Role.EXTERNAL_REVIEWER))
        data = response.json()
        assert any(r["id"] == contact.pk for r in data["results"])

    def test_role_filter_excludes_non_match(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, role=Contact.Role.AUTHOR))
        data = response.json()
        assert not any(r["id"] == contact.pk for r in data["results"])

    def test_result_shape(self, client, user, membership, contact):
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Dupont"))
        data = response.json()
        assert data["results"]
        r = data["results"][0]
        assert "id" in r
        assert "name" in r
        assert "affiliation" in r

    def test_max_10_results(self, client, user, membership):
        for i in range(15):
            Contact.objects.create(
                journal=membership.journal,
                first_name=f"Test{i}",
                last_name="Smith",
            )
        client.force_login(user)
        response = client.get(_search_url(membership.journal, q="Smith"))
        data = response.json()
        assert len(data["results"]) <= 10
