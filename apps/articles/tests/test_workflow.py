import pytest
from django_fsm import TransitionNotAllowed

from apps.articles.models import Article


@pytest.mark.django_db
class TestArticleWorkflow:
    def test_initial_state(self, article):
        assert article.state == Article.State.PENDING

    def test_pending_to_received(self, article):
        article.mark_received()
        assert article.state == Article.State.RECEIVED

    def test_cannot_send_to_review_from_pending(self, article):
        with pytest.raises(TransitionNotAllowed):
            article.send_to_review()

    def test_cannot_validate_from_pending(self, article):
        with pytest.raises(TransitionNotAllowed):
            article.validate()

    def test_send_to_review(self, received_article):
        received_article.send_to_review()
        assert received_article.state == Article.State.IN_REVIEW

    def test_cancel_review(self, received_article):
        received_article.send_to_review()
        received_article.cancel_review()
        assert received_article.state == Article.State.RECEIVED

    def test_mark_reviews_received(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        assert received_article.state == Article.State.REVIEWS_RECEIVED

    def test_send_to_author(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.send_to_author()
        assert received_article.state == Article.State.IN_AUTHOR_REVISION

    def test_mark_as_revised(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.send_to_author()
        received_article.mark_as_revised()
        assert received_article.state == Article.State.REVISED

    def test_second_review_round_from_revised(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.send_to_author()
        received_article.mark_as_revised()
        received_article.send_to_review()
        assert received_article.state == Article.State.IN_REVIEW

    def test_validate_after_reviews_received(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.validate()
        assert received_article.state == Article.State.VALIDATED

    def test_validate_after_revised(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.send_to_author()
        received_article.mark_as_revised()
        received_article.validate()
        assert received_article.state == Article.State.VALIDATED

    def test_request_more_revision(self, received_article):
        received_article.send_to_review()
        received_article.mark_reviews_received()
        received_article.send_to_author()
        received_article.mark_as_revised()
        received_article.request_more_revision()
        assert received_article.state == Article.State.IN_AUTHOR_REVISION

    def test_cannot_validate_from_received(self, received_article):
        with pytest.raises(TransitionNotAllowed):
            received_article.validate()

    def test_cannot_validate_from_in_review(self, received_article):
        received_article.send_to_review()
        with pytest.raises(TransitionNotAllowed):
            received_article.validate()
