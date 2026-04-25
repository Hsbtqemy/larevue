import pytest
from django.urls import reverse

from apps.contacts.models import Contact


def _create_url(journal):
    return reverse("contacts:create", kwargs={"slug": journal.slug})


@pytest.mark.django_db
class TestContactCreateView:
    def test_unauthenticated_redirects(self, client, journal):
        response = client.get(_create_url(journal))
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_non_member_gets_403(self, client, db):
        from apps.accounts.models import User
        from apps.journals.models import Journal

        j = Journal.objects.create(name="Autre", slug="autre-contact")
        u = User.objects.create_user(email="x@x.com", password="pass")
        client.force_login(u)
        response = client.get(_create_url(j))
        assert response.status_code == 403

    def test_member_can_get_form(self, client, user, membership):
        client.force_login(user)
        response = client.get(_create_url(membership.journal))
        assert response.status_code == 200
        assert "form" in response.context

    def test_valid_post_creates_contact(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "first_name": "Marie",
            "last_name": "Curie",
            "email": "marie@example.com",
            "affiliation": "CNRS",
            "usual_roles": [Contact.Role.AUTHOR],
            "notes": "",
        })
        assert response.status_code == 302
        c = Contact.objects.get(journal=membership.journal, last_name="Curie")
        assert c.first_name == "Marie"
        assert Contact.Role.AUTHOR in c.usual_roles

    def test_contact_belongs_to_journal(self, client, user, membership):
        client.force_login(user)
        client.post(_create_url(membership.journal), {
            "first_name": "Pierre",
            "last_name": "Dupont",
            "email": "",
            "affiliation": "",
            "usual_roles": [],
            "notes": "",
        })
        c = Contact.objects.get(last_name="Dupont")
        assert c.journal == membership.journal

    def test_redirects_to_dashboard_after_create(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "first_name": "Anne",
            "last_name": "Martin",
            "email": "",
            "affiliation": "",
            "usual_roles": [],
            "notes": "",
        })
        assert response.status_code == 302
        assert response["Location"] == reverse(
            "journal_dashboard", kwargs={"slug": membership.journal.slug}
        )

    def test_flash_message_on_create(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "first_name": "Luc",
            "last_name": "Bernard",
            "email": "",
            "affiliation": "",
            "usual_roles": [],
            "notes": "",
        }, follow=True)
        messages = list(response.context["messages"])
        assert any("Luc Bernard" in str(m) for m in messages)

    def test_invalid_post_rerenders_form(self, client, user, membership):
        client.force_login(user)
        response = client.post(_create_url(membership.journal), {
            "first_name": "",
            "last_name": "",
        })
        assert response.status_code == 200
        assert response.context["form"].errors
