import pytest
from django_fsm import TransitionNotAllowed

from apps.articles.models import Article


@pytest.mark.django_db
class TestArticleWorkflow:
    def test_initial_state(self, article):
        assert article.state == Article.State.RECEIVED

    def test_send_to_review(self, article):
        article.send_to_review()
        assert article.state == Article.State.IN_REVIEW

    def test_cancel_review(self, article):
        article.send_to_review()
        article.cancel_review()
        assert article.state == Article.State.RECEIVED

    def test_mark_reviews_received(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        assert article.state == Article.State.REVIEWS_RECEIVED

    def test_send_to_author(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.send_to_author()
        assert article.state == Article.State.IN_AUTHOR_REVISION

    def test_mark_as_revised(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.send_to_author()
        article.mark_as_revised()
        assert article.state == Article.State.REVISED

    def test_second_review_round_from_revised(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.send_to_author()
        article.mark_as_revised()
        article.send_to_review()
        assert article.state == Article.State.IN_REVIEW

    def test_validate_after_reviews_received(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.validate()
        assert article.state == Article.State.VALIDATED

    def test_validate_after_revised(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.send_to_author()
        article.mark_as_revised()
        article.validate()
        assert article.state == Article.State.VALIDATED

    def test_request_more_revision(self, article):
        article.send_to_review()
        article.mark_reviews_received()
        article.send_to_author()
        article.mark_as_revised()
        article.request_more_revision()
        assert article.state == Article.State.IN_AUTHOR_REVISION

    def test_cannot_validate_from_received(self, article):
        with pytest.raises(TransitionNotAllowed):
            article.validate()

    def test_cannot_validate_from_in_review(self, article):
        article.send_to_review()
        with pytest.raises(TransitionNotAllowed):
            article.validate()
