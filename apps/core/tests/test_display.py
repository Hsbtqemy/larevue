import pytest

from apps.core.display import ARTICLE_TONES, ISSUE_TONES, VERDICT_LABELS, VERDICT_TONES
from apps.issues.models import Issue
from apps.articles.models import Article
from apps.reviews.models import ReviewRequest


class TestIssueTones:
    def test_all_states_covered(self):
        issue_states = {s.value for s in Issue.State}
        assert issue_states == set(ISSUE_TONES.keys())

    @pytest.mark.parametrize("state,expected_tone", [
        (Issue.State.UNDER_REVIEW, "neutral"),
        (Issue.State.ACCEPTED, "info"),
        (Issue.State.IN_PRODUCTION, "active"),
        (Issue.State.SENT_TO_PUBLISHER, "progress-tone"),
        (Issue.State.PUBLISHED, "done"),
        (Issue.State.REFUSED, "refused"),
    ])
    def test_tone(self, state, expected_tone):
        assert ISSUE_TONES[state] == expected_tone

    @pytest.mark.django_db
    @pytest.mark.parametrize("state", list(Issue.State))
    def test_get_badge_tone_on_instance(self, state, journal):
        issue = Issue(journal=journal, number="1", thematic_title="T", editor_name="E", state=state)
        assert issue.get_badge_tone() == ISSUE_TONES[state]


class TestArticleTones:
    def test_all_states_covered(self):
        article_states = {s.value for s in Article.State}
        assert article_states == set(ARTICLE_TONES.keys())

    @pytest.mark.parametrize("state,expected_tone", [
        (Article.State.RECEIVED, "neutral"),
        (Article.State.IN_REVIEW, "active"),
        (Article.State.REVIEWS_RECEIVED, "info"),
        (Article.State.IN_AUTHOR_REVISION, "progress-tone"),
        (Article.State.REVISED, "info"),
        (Article.State.VALIDATED, "done"),
    ])
    def test_tone(self, state, expected_tone):
        assert ARTICLE_TONES[state] == expected_tone

    @pytest.mark.django_db
    @pytest.mark.parametrize("state", list(Article.State))
    def test_get_badge_tone_on_instance(self, state, issue):
        article = Article(issue=issue, title="T", state=state)
        assert article.get_badge_tone() == ARTICLE_TONES[state]


class TestVerdictTones:
    def test_all_verdicts_covered(self):
        verdicts = {v.value for v in ReviewRequest.Verdict}
        assert verdicts == set(VERDICT_TONES.keys())
        assert verdicts == set(VERDICT_LABELS.keys())

    @pytest.mark.parametrize("verdict,expected_tone", [
        (ReviewRequest.Verdict.FAVORABLE, "done"),
        (ReviewRequest.Verdict.NEEDS_REVISION, "progress-tone"),
        (ReviewRequest.Verdict.UNFAVORABLE, "refused"),
    ])
    def test_tone(self, verdict, expected_tone):
        assert VERDICT_TONES[verdict] == expected_tone

    @pytest.mark.parametrize("verdict,expected_label", [
        (ReviewRequest.Verdict.FAVORABLE, "Favorable"),
        (ReviewRequest.Verdict.NEEDS_REVISION, "Révision requise"),
        (ReviewRequest.Verdict.UNFAVORABLE, "Défavorable"),
    ])
    def test_label(self, verdict, expected_label):
        assert VERDICT_LABELS[verdict] == expected_label
