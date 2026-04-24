import pytest
from django_fsm import TransitionNotAllowed

from apps.issues.models import Issue


@pytest.mark.django_db
class TestIssueWorkflow:
    def test_initial_state(self, issue):
        assert issue.state == Issue.State.UNDER_REVIEW

    def test_accept(self, issue):
        issue.accept()
        issue.save()
        assert issue.state == Issue.State.ACCEPTED

    def test_refuse(self, issue):
        issue.refuse()
        issue.save()
        assert issue.state == Issue.State.REFUSED

    def test_refused_is_terminal(self, issue):
        issue.refuse()
        with pytest.raises(TransitionNotAllowed):
            issue.accept()

    def test_cannot_refuse_after_acceptance(self, issue):
        issue.accept()
        with pytest.raises(TransitionNotAllowed):
            issue.refuse()

    def test_full_forward_workflow(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.reviews_received_return_to_authors()
        issue.v2_received_final_check()
        issue.send_to_publisher()
        issue.mark_as_published()
        assert issue.state == Issue.State.PUBLISHED

    def test_rollback_to_under_review(self, issue):
        issue.accept()
        issue.reopen_for_review()
        assert issue.state == Issue.State.UNDER_REVIEW

    def test_rollback_recall_reviewers(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.recall_reviewers()
        assert issue.state == Issue.State.ACCEPTED

    def test_rollback_recall_to_authors(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.reviews_received_return_to_authors()
        issue.recall_to_authors()
        assert issue.state == Issue.State.IN_REVIEW

    def test_rollback_reopen_revision(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.reviews_received_return_to_authors()
        issue.v2_received_final_check()
        issue.reopen_revision()
        assert issue.state == Issue.State.IN_REVISION

    def test_rollback_recall_final_check(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.reviews_received_return_to_authors()
        issue.v2_received_final_check()
        issue.send_to_publisher()
        issue.recall_final_check()
        assert issue.state == Issue.State.FINAL_CHECK

    def test_unpublish(self, issue):
        issue.accept()
        issue.send_to_reviewers()
        issue.reviews_received_return_to_authors()
        issue.v2_received_final_check()
        issue.send_to_publisher()
        issue.mark_as_published()
        issue.unpublish()
        assert issue.state == Issue.State.SENT_TO_PUBLISHER
