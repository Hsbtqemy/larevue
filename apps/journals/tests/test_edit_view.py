import pytest
from django.urls import reverse

from apps.journals.models import Journal


def _url(journal):
    return reverse("journal_edit", kwargs={"slug": journal.slug})


@pytest.mark.django_db
class TestJournalEditViewGet:
    def test_member_can_access(self, client, user, membership, journal):
        client.force_login(user)
        res = client.get(_url(journal))
        assert res.status_code == 200

    def test_non_member_gets_403(self, client, journal):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.get(_url(journal))
        assert res.status_code == 403

    def test_unauthenticated_redirects(self, client, journal):
        res = client.get(_url(journal))
        assert res.status_code == 302
        assert "/accounts/" in res["Location"]

    def test_form_prepopulated_with_journal_name(self, client, user, membership, journal):
        client.force_login(user)
        res = client.get(_url(journal))
        assert journal.name in res.content.decode()

    def test_unknown_slug_returns_404(self, client, user):
        client.force_login(user)
        res = client.get(reverse("journal_edit", kwargs={"slug": "nonexistent"}))
        assert res.status_code == 404


@pytest.mark.django_db
class TestJournalEditViewPost:
    def test_valid_post_saves_name(self, client, user, membership, journal):
        client.force_login(user)
        res = client.post(_url(journal), {
            "name": "Nouvelle revue",
            "accent_color": "olive",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        assert res.status_code == 302
        journal.refresh_from_db()
        assert journal.name == "Nouvelle revue"

    def test_valid_post_saves_accent_color(self, client, user, membership, journal):
        client.force_login(user)
        client.post(_url(journal), {
            "name": journal.name,
            "accent_color": "plum",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        journal.refresh_from_db()
        assert journal.accent_color == "plum"

    def test_valid_post_saves_institutional_fields(self, client, user, membership, journal):
        client.force_login(user)
        client.post(_url(journal), {
            "name": journal.name,
            "accent_color": "terracotta",
            "description": "",
            "directors": "Marie Dupont",
            "publisher": "PUF",
            "issn_print": "1234-5678",
            "issn_online": "8765-4321",
            "periodicity": "Semestrielle",
            "founded_year": "2005",
            "website": "https://example.com",
        })
        journal.refresh_from_db()
        assert journal.directors == "Marie Dupont"
        assert journal.publisher == "PUF"
        assert journal.issn_print == "1234-5678"
        assert journal.issn_online == "8765-4321"
        assert journal.periodicity == "Semestrielle"
        assert journal.founded_year == 2005
        assert journal.website == "https://example.com"

    def test_valid_post_redirects_back_to_edit(self, client, user, membership, journal):
        client.force_login(user)
        res = client.post(_url(journal), {
            "name": journal.name,
            "accent_color": "terracotta",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        assert res.status_code == 302
        assert res["Location"] == _url(journal)

    def test_invalid_name_rerenders_with_errors(self, client, user, membership, journal):
        client.force_login(user)
        res = client.post(_url(journal), {
            "name": "",
            "accent_color": "terracotta",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        assert res.status_code == 200

    def test_duplicate_name_rerenders_with_errors(self, client, user, membership, journal):
        other = Journal.objects.create(name="Autre revue", slug="autre-revue-edit")
        client.force_login(user)
        res = client.post(_url(journal), {
            "name": other.name,
            "accent_color": "terracotta",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        assert res.status_code == 200
        journal.refresh_from_db()
        assert journal.name != other.name

    def test_non_member_cannot_post(self, client, journal):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.post(_url(journal), {"name": "Hack", "accent_color": "terracotta"})
        assert res.status_code == 403
        journal.refresh_from_db()
        assert journal.name != "Hack"

    def test_invalid_accent_rerenders(self, client, user, membership, journal):
        client.force_login(user)
        original_accent = journal.accent_color
        res = client.post(_url(journal), {
            "name": journal.name,
            "accent_color": "invalid-color",
            "description": "",
            "directors": "", "publisher": "", "issn_print": "",
            "issn_online": "", "periodicity": "", "founded_year": "", "website": "",
        })
        assert res.status_code == 200
        journal.refresh_from_db()
        assert journal.accent_color == original_accent
