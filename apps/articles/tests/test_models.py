import pytest

from apps.articles.models import Article, ArticleVersion, InternalNote


@pytest.mark.django_db
class TestArticle:
    def test_str(self, article):
        assert str(article) == "Article de test"

    def test_displayed_author_name_from_contact(self, article):
        assert article.displayed_author_name == "Jean Dupont"

    def test_displayed_author_name_override(self, article):
        article.author_name_override = "J. Dupont et al."
        assert article.displayed_author_name == "J. Dupont et al."

    def test_displayed_author_name_no_author(self, issue):
        a = Article.objects.create(issue=issue, title="Sans auteur")
        assert a.displayed_author_name == ""


@pytest.mark.django_db
class TestArticleVersion:
    def test_version_number_auto_increments(self, article, user):
        import tempfile

        from django.core.files.base import ContentFile

        v1 = ArticleVersion.objects.create(
            article=article,
            file=ContentFile(b"content", name="v1.pdf"),
            uploaded_by=user,
        )
        v2 = ArticleVersion.objects.create(
            article=article,
            file=ContentFile(b"content", name="v2.pdf"),
            uploaded_by=user,
        )
        assert v1.version_number == 1
        assert v2.version_number == 2

    def test_version_number_independent_per_article(self, issue, contact, user):
        from django.core.files.base import ContentFile

        a1 = Article.objects.create(issue=issue, title="A1", author=contact)
        a2 = Article.objects.create(issue=issue, title="A2", author=contact)
        ArticleVersion.objects.create(
            article=a1, file=ContentFile(b"x", name="f.pdf"), uploaded_by=user
        )
        v = ArticleVersion.objects.create(
            article=a2, file=ContentFile(b"x", name="f.pdf"), uploaded_by=user
        )
        assert v.version_number == 1


@pytest.mark.django_db
class TestInternalNote:
    def test_automatic_flag(self, article, user):
        note = InternalNote.objects.create(
            article=article, author=user, content="Changement d'état.", is_automatic=True
        )
        assert note.is_automatic

    def test_str_includes_article_title(self, article, user):
        note = InternalNote.objects.create(article=article, author=user, content="OK")
        assert "Article de test" in str(note)
