import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.articles.models import Article, ArticleVersion, InternalNote
from apps.issues.models import Issue


def _url(journal, issue, article):
    return reverse(
        "articles:file_upload",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _upload(client, journal, issue, article, filename="doc.pdf", content=b"pdf", comment=""):
    return client.post(
        _url(journal, issue, article),
        {"file": ContentFile(content, name=filename), "comment": comment},
    )


@pytest.fixture
def in_review_article(received_article):
    received_article.send_to_review()
    received_article.save()
    return received_article


@pytest.fixture
def validated_article(received_article):
    received_article.send_to_review()
    received_article.mark_reviews_received()
    received_article.validate()
    received_article.save()
    return received_article


@pytest.fixture
def in_author_revision_article(received_article):
    received_article.send_to_review()
    received_article.mark_reviews_received()
    received_article.send_to_author()
    received_article.save()
    return received_article


@pytest.mark.django_db
class TestArticleFileUploadView:

    # ── Auth / permissions ────────────────────────────────────────────────────

    def test_requires_login(self, client, journal, issue, article):
        res = _upload(client, journal, issue, article)
        assert res.status_code == 302

    def test_non_member_forbidden(self, client, user, journal, issue, article):
        client.force_login(user)
        res = _upload(client, journal, issue, article)
        assert res.status_code == 403

    def test_archived_issue_returns_403(self, client, user, membership, journal, issue, article):
        Issue.objects.filter(pk=issue.pk).update(state=Issue.State.PUBLISHED)
        client.force_login(user)
        res = _upload(client, journal, issue, article)
        assert res.status_code == 403

    # ── Blocked states ────────────────────────────────────────────────────────

    def test_in_review_returns_403(self, client, user, membership, journal, issue, in_review_article):
        client.force_login(user)
        res = _upload(client, journal, issue, in_review_article)
        assert res.status_code == 403

    def test_validated_returns_403(self, client, user, membership, journal, issue, validated_article):
        client.force_login(user)
        res = _upload(client, journal, issue, validated_article)
        assert res.status_code == 403

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_file_returns_400(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = client.post(_url(journal, issue, article), {"comment": ""})
        assert res.status_code == 400

    # ── pending → received ────────────────────────────────────────────────────

    def test_pending_upload_transitions_to_received(self, client, user, membership, journal, issue, article):
        assert article.state == Article.State.PENDING
        client.force_login(user)
        _upload(client, journal, issue, article)
        assert Article.objects.get(pk=article.pk).state == Article.State.RECEIVED

    def test_pending_upload_creates_v1(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _upload(client, journal, issue, article)
        assert ArticleVersion.objects.filter(article=article, version_number=1).exists()

    def test_pending_upload_note_content(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _upload(client, journal, issue, article)
        note = InternalNote.objects.filter(article=article, is_automatic=True).last()
        assert note is not None
        assert "a déposé le fichier de l'article" in note.content

    def test_pending_upload_with_description_in_note(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        _upload(client, journal, issue, article, comment="version initiale")
        note = InternalNote.objects.filter(article=article, is_automatic=True).last()
        assert "a déposé le fichier de l'article" in note.content
        assert "version initiale" in note.content

    # ── subsequent uploads ────────────────────────────────────────────────────

    def test_subsequent_upload_keeps_state(self, client, user, membership, journal, issue, received_article):
        client.force_login(user)
        _upload(client, journal, issue, received_article)
        assert Article.objects.get(pk=received_article.pk).state == Article.State.RECEIVED

    def test_subsequent_upload_increments_version(self, client, user, membership, journal, issue, received_article):
        client.force_login(user)
        _upload(client, journal, issue, received_article)
        _upload(client, journal, issue, received_article)
        numbers = list(
            ArticleVersion.objects.filter(article=received_article)
            .order_by("version_number")
            .values_list("version_number", flat=True)
        )
        assert numbers == [1, 2]

    def test_subsequent_upload_note_content(self, client, user, membership, journal, issue, received_article):
        client.force_login(user)
        ArticleVersion.objects.create(
            article=received_article,
            file=ContentFile(b"v1", name="v1.pdf"),
            uploaded_by=user,
        )
        _upload(client, journal, issue, received_article)
        note = InternalNote.objects.filter(article=received_article, is_automatic=True).last()
        assert "a déposé la version v2" in note.content

    def test_subsequent_upload_with_description_in_note(self, client, user, membership, journal, issue, received_article):
        client.force_login(user)
        _upload(client, journal, issue, received_article, comment="corrections mineures")
        note = InternalNote.objects.filter(article=received_article, is_automatic=True).last()
        assert "a déposé la version v" in note.content
        assert "corrections mineures" in note.content

    def test_in_author_revision_upload_allowed(self, client, user, membership, journal, issue, in_author_revision_article):
        client.force_login(user)
        res = _upload(client, journal, issue, in_author_revision_article)
        assert res.status_code == 302
        assert ArticleVersion.objects.filter(article=in_author_revision_article).exists()

    # ── Redirect ──────────────────────────────────────────────────────────────

    def test_redirects_to_article_detail(self, client, user, membership, journal, issue, article):
        client.force_login(user)
        res = _upload(client, journal, issue, article)
        assert res.status_code == 302
        expected = reverse(
            "articles:detail",
            kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
        )
        assert res["Location"] == expected
