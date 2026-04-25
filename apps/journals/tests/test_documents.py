import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.journals.models import Journal, JournalDocument


def _create_url(journal):
    return reverse("journal_document_create", kwargs={"slug": journal.slug})


def _delete_url(journal, doc):
    return reverse("journal_document_delete", kwargs={"slug": journal.slug, "doc_id": doc.pk})


def _download_url(journal, doc):
    return reverse("journal_document_download", kwargs={"slug": journal.slug, "doc_id": doc.pk})


def _make_file(name="doc.pdf", content=b"pdf content"):
    return ContentFile(content, name=name)


@pytest.fixture
def doc(journal, user):
    return JournalDocument.objects.create(
        journal=journal,
        name="Règlement intérieur",
        file=ContentFile(b"pdf content", name="reglement.pdf"),
        uploaded_by=user,
    )


# ------------------------------------------------------------------ #
# JournalDocumentCreateView                                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestJournalDocumentCreateView:
    def test_member_can_upload(self, client, user, membership, journal):
        client.force_login(user)
        res = client.post(
            _create_url(journal),
            {"name": "Appel à contributions", "description": "", "file": _make_file()},
        )
        assert res.status_code == 302
        assert JournalDocument.objects.filter(journal=journal, name="Appel à contributions").exists()

    def test_uploaded_by_is_set(self, client, user, membership, journal):
        client.force_login(user)
        client.post(
            _create_url(journal),
            {"name": "Statuts", "description": "", "file": _make_file()},
        )
        doc = JournalDocument.objects.get(journal=journal, name="Statuts")
        assert doc.uploaded_by == user

    def test_non_member_gets_403(self, client, journal):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.post(
            _create_url(journal),
            {"name": "X", "description": "", "file": _make_file()},
        )
        assert res.status_code == 403

    def test_invalid_form_does_not_create(self, client, user, membership, journal):
        client.force_login(user)
        res = client.post(_create_url(journal), {"name": "", "description": ""})
        assert res.status_code == 302
        assert JournalDocument.objects.filter(journal=journal).count() == 0

    def test_file_too_large_is_rejected(self, client, user, membership, journal):
        client.force_login(user)
        big = ContentFile(b"x" * (26 * 1024 * 1024), name="big.pdf")
        res = client.post(
            _create_url(journal),
            {"name": "Trop gros", "description": "", "file": big},
        )
        assert res.status_code == 302
        assert not JournalDocument.objects.filter(journal=journal, name="Trop gros").exists()

    def test_journal_can_have_multiple_documents(self, client, user, membership, journal):
        client.force_login(user)
        for name in ["Doc A", "Doc B", "Doc C"]:
            client.post(
                _create_url(journal),
                {"name": name, "description": "", "file": _make_file(f"{name}.pdf")},
            )
        assert JournalDocument.objects.filter(journal=journal).count() == 3


# ------------------------------------------------------------------ #
# JournalDocumentDeleteView                                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestJournalDocumentDeleteView:
    def test_member_can_delete(self, client, user, membership, journal, doc):
        client.force_login(user)
        res = client.post(_delete_url(journal, doc))
        assert res.status_code == 302
        assert not JournalDocument.objects.filter(pk=doc.pk).exists()

    def test_non_member_gets_403(self, client, journal, doc):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.post(_delete_url(journal, doc))
        assert res.status_code == 403
        assert JournalDocument.objects.filter(pk=doc.pk).exists()

    def test_doc_from_other_journal_is_404(self, client, user, membership, journal):
        other = Journal.objects.create(name="Autre revue", slug="autre-revue-doc")
        other_doc = JournalDocument.objects.create(
            journal=other, name="Doc autre", file=ContentFile(b"x", name="x.pdf")
        )
        client.force_login(user)
        url = reverse("journal_document_delete", kwargs={"slug": journal.slug, "doc_id": other_doc.pk})
        res = client.post(url)
        assert res.status_code == 404


# ------------------------------------------------------------------ #
# JournalDocumentDownloadView                                          #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestJournalDocumentDownloadView:
    def test_member_can_download(self, client, user, membership, journal, doc):
        client.force_login(user)
        res = client.get(_download_url(journal, doc))
        assert res.status_code == 200
        assert res.has_header("Content-Disposition")

    def test_non_member_cannot_download(self, client, journal, doc):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.get(_download_url(journal, doc))
        assert res.status_code == 403

    def test_doc_from_other_journal_is_404(self, client, user, membership, journal):
        other = Journal.objects.create(name="Autre revue", slug="autre-revue-dl")
        other_doc = JournalDocument.objects.create(
            journal=other, name="Doc autre", file=ContentFile(b"x", name="x.pdf")
        )
        client.force_login(user)
        url = reverse("journal_document_download", kwargs={"slug": journal.slug, "doc_id": other_doc.pk})
        res = client.get(url)
        assert res.status_code == 404


# ------------------------------------------------------------------ #
# Model & ordering                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestJournalDocumentModel:
    def test_ordering_most_recent_first(self, journal, user):
        d1 = JournalDocument.objects.create(
            journal=journal, name="Premier", file=ContentFile(b"x", name="a.pdf"), uploaded_by=user
        )
        d2 = JournalDocument.objects.create(
            journal=journal, name="Deuxième", file=ContentFile(b"x", name="b.pdf"), uploaded_by=user
        )
        docs = list(JournalDocument.objects.filter(journal=journal))
        assert docs[0].pk == d2.pk
        assert docs[1].pk == d1.pk

    def test_cascade_delete_on_journal_delete(self, journal, user):
        JournalDocument.objects.create(
            journal=journal, name="Doc", file=ContentFile(b"x", name="doc.pdf"), uploaded_by=user
        )
        journal.hard_delete()
        assert JournalDocument.objects.filter(journal_id=journal.pk).count() == 0
