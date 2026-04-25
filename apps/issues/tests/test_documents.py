import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.articles.models import InternalNote
from apps.issues.models import Issue, IssueDocument


# ------------------------------------------------------------------ #
# URL helpers                                                          #
# ------------------------------------------------------------------ #

def _create_url(journal, issue):
    return reverse("issues:document_create", kwargs={"slug": journal.slug, "issue_id": issue.pk})


def _delete_url(journal, issue, doc):
    return reverse("issues:document_delete", kwargs={"slug": journal.slug, "issue_id": issue.pk, "doc_id": doc.pk})


def _download_url(journal, issue, doc):
    return reverse("issues:document_download", kwargs={"slug": journal.slug, "issue_id": issue.pk, "doc_id": doc.pk})


def _make_file(name="doc.pdf", content=b"pdf content"):
    return ContentFile(content, name=name)


@pytest.fixture
def doc(db, issue, user):
    return IssueDocument.objects.create(
        issue=issue,
        name="Projet de numéro",
        file=ContentFile(b"pdf content", name="projet.pdf"),
        uploaded_by=user,
    )


# ------------------------------------------------------------------ #
# IssueDocumentCreateView                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestIssueDocumentCreateView:
    def test_member_can_upload(self, client, user, membership, journal, issue):
        client.force_login(user)
        res = client.post(
            _create_url(journal, issue),
            {"name": "Appel à contributions", "description": "", "file": _make_file()},
        )
        assert res.status_code == 302
        assert IssueDocument.objects.filter(issue=issue, name="Appel à contributions").exists()

    def test_auto_note_created_on_upload(self, client, user, membership, journal, issue):
        client.force_login(user)
        client.post(
            _create_url(journal, issue),
            {"name": "Calendrier", "description": "", "file": _make_file()},
        )
        note = InternalNote.objects.filter(issue=issue, is_automatic=True).first()
        assert note is not None
        assert "Calendrier" in note.content

    def test_uploaded_by_is_set(self, client, user, membership, journal, issue):
        client.force_login(user)
        client.post(
            _create_url(journal, issue),
            {"name": "Sommaire", "description": "", "file": _make_file()},
        )
        doc = IssueDocument.objects.get(issue=issue, name="Sommaire")
        assert doc.uploaded_by == user

    def test_non_member_gets_403(self, client, journal, issue):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.post(
            _create_url(journal, issue),
            {"name": "X", "description": "", "file": _make_file()},
        )
        assert res.status_code == 403

    def test_archived_issue_gets_403(self, client, user, membership, journal, issue):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.post(
            _create_url(journal, issue),
            {"name": "X", "description": "", "file": _make_file()},
        )
        assert res.status_code == 403

    def test_file_too_large_is_rejected(self, client, user, membership, journal, issue):
        client.force_login(user)
        big = ContentFile(b"x" * (26 * 1024 * 1024), name="big.pdf")
        res = client.post(
            _create_url(journal, issue),
            {"name": "Trop gros", "description": "", "file": big},
        )
        # Invalid form → redirect without creating document
        assert res.status_code == 302
        assert not IssueDocument.objects.filter(issue=issue, name="Trop gros").exists()

    def test_issue_can_have_multiple_documents(self, client, user, membership, journal, issue):
        client.force_login(user)
        for name in ["Doc A", "Doc B", "Doc C"]:
            client.post(
                _create_url(journal, issue),
                {"name": name, "description": "", "file": _make_file(f"{name}.pdf")},
            )
        assert IssueDocument.objects.filter(issue=issue).count() == 3


# ------------------------------------------------------------------ #
# IssueDocumentDeleteView                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestIssueDocumentDeleteView:
    def test_member_can_delete(self, client, user, membership, journal, issue, doc):
        client.force_login(user)
        res = client.post(_delete_url(journal, issue, doc))
        assert res.status_code == 302
        assert not IssueDocument.objects.filter(pk=doc.pk).exists()

    def test_auto_note_created_on_delete(self, client, user, membership, journal, issue, doc):
        doc_name = doc.name
        client.force_login(user)
        client.post(_delete_url(journal, issue, doc))
        note = InternalNote.objects.filter(issue=issue, is_automatic=True).last()
        assert note is not None
        assert doc_name in note.content

    def test_non_member_gets_403(self, client, journal, issue, doc):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.post(_delete_url(journal, issue, doc))
        assert res.status_code == 403
        assert IssueDocument.objects.filter(pk=doc.pk).exists()

    def test_archived_issue_gets_403(self, client, user, membership, journal, issue, doc):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = client.post(_delete_url(journal, issue, doc))
        assert res.status_code == 403

    def test_doc_from_other_issue_is_404(self, client, user, membership, journal, issue, doc):
        other_issue = Issue.objects.create(
            journal=journal, number="99", thematic_title="Autre", editor_name="Ed"
        )
        client.force_login(user)
        url = reverse(
            "issues:document_delete",
            kwargs={"slug": journal.slug, "issue_id": other_issue.pk, "doc_id": doc.pk},
        )
        res = client.post(url)
        assert res.status_code == 404


# ------------------------------------------------------------------ #
# IssueDocumentDownloadView                                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestIssueDocumentDownloadView:
    def test_member_can_download(self, client, user, membership, journal, issue, doc):
        client.force_login(user)
        res = client.get(_download_url(journal, issue, doc))
        assert res.status_code == 200
        assert res.has_header("Content-Disposition")

    def test_non_member_cannot_download(self, client, journal, issue, doc):
        from apps.accounts.models import User
        other = User.objects.create_user(email="other@test.com", password="pass")
        client.force_login(other)
        res = client.get(_download_url(journal, issue, doc))
        assert res.status_code == 403

    def test_doc_from_other_issue_is_404(self, client, user, membership, journal, issue, doc):
        other_issue = Issue.objects.create(
            journal=journal, number="99", thematic_title="Autre", editor_name="Ed"
        )
        client.force_login(user)
        url = reverse(
            "issues:document_download",
            kwargs={"slug": journal.slug, "issue_id": other_issue.pk, "doc_id": doc.pk},
        )
        res = client.get(url)
        assert res.status_code == 404


# ------------------------------------------------------------------ #
# Model & ordering                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestIssueDocumentModel:
    def test_ordering_most_recent_first(self, issue, user):
        d1 = IssueDocument.objects.create(
            issue=issue, name="Premier", file=ContentFile(b"x", name="a.pdf"), uploaded_by=user
        )
        d2 = IssueDocument.objects.create(
            issue=issue, name="Deuxième", file=ContentFile(b"x", name="b.pdf"), uploaded_by=user
        )
        docs = list(IssueDocument.objects.filter(issue=issue))
        assert docs[0].pk == d2.pk
        assert docs[1].pk == d1.pk

    def test_cascade_delete_on_issue_hard_delete(self, issue, user):
        IssueDocument.objects.create(
            issue=issue, name="Doc", file=ContentFile(b"x", name="doc.pdf"), uploaded_by=user
        )
        issue.hard_delete()
        assert IssueDocument.objects.filter(issue_id=issue.pk).count() == 0
