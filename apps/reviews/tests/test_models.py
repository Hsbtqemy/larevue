import pytest
from django.utils import timezone

from apps.articles.models import ArticleVersion
from apps.reviews.models import ReviewRequest


@pytest.fixture
def article_version(article, user):
    from django.core.files.base import ContentFile

    return ArticleVersion.objects.create(
        article=article,
        file=ContentFile(b"content", name="v1.pdf"),
        uploaded_by=user,
    )


@pytest.fixture
def review_request(db, article, article_version, contact):
    return ReviewRequest.objects.create(
        article=article,
        article_version=article_version,
        reviewer=contact,
        reviewer_name_snapshot=contact.full_name,
        deadline=timezone.now().date(),
    )


@pytest.mark.django_db
class TestReviewRequest:
    def test_str(self, review_request):
        assert "Jean Dupont" in str(review_request)
        assert "Article de test" in str(review_request)

    def test_is_overdue_when_deadline_passed(self, review_request):
        from datetime import timedelta

        review_request.deadline = timezone.now().date() - timedelta(days=1)
        assert review_request.is_overdue

    def test_not_overdue_when_deadline_today(self, review_request):
        review_request.deadline = timezone.now().date()
        assert not review_request.is_overdue

    def test_not_overdue_when_received(self, review_request):
        from datetime import timedelta

        review_request.deadline = timezone.now().date() - timedelta(days=5)
        review_request.state = ReviewRequest.State.RECEIVED
        assert not review_request.is_overdue

    def test_reviewer_name_snapshot_preserved(self, review_request):
        review_request.reviewer.first_name = "Jacques"
        review_request.reviewer.save()
        assert review_request.reviewer_name_snapshot == "Jean Dupont"
