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
        issue.start_production()
        issue.send_to_publisher()
        issue.mark_as_published()
        assert issue.state == Issue.State.PUBLISHED

    def test_rollback_to_under_review(self, issue):
        issue.accept()
        issue.reopen_for_review()
        assert issue.state == Issue.State.UNDER_REVIEW

    def test_rollback_pause_production(self, issue):
        issue.accept()
        issue.start_production()
        issue.pause_production()
        assert issue.state == Issue.State.ACCEPTED

    def test_rollback_recall_from_publisher(self, issue):
        issue.accept()
        issue.start_production()
        issue.send_to_publisher()
        issue.recall_from_publisher()
        assert issue.state == Issue.State.IN_PRODUCTION

    def test_unpublish(self, issue):
        issue.accept()
        issue.start_production()
        issue.send_to_publisher()
        issue.mark_as_published()
        issue.unpublish()
        assert issue.state == Issue.State.SENT_TO_PUBLISHER
