import pytest
from django.core import mail

from apps.core.mail import send_reviewer_added
from apps.journals.models import Journal


@pytest.mark.django_db
class TestSendReviewerAdded:
    def test_says_revue_for_periodical(self, journal):
        send_reviewer_added(
            email="relecteur@example.com",
            reviewer_name="Jean Dupont",
            journal_name=journal.name,
            profile_url="https://example.com/profil",
            journal=journal,
        )
        body = mail.outbox[0].body
        assert "de la revue" in body
        assert "du projet" not in body

    def test_says_projet_for_standalone(self, db):
        project = Journal.objects.create(name="Actes 2026", kind=Journal.Kind.STANDALONE)
        send_reviewer_added(
            email="relecteur@example.com",
            reviewer_name="Jean Dupont",
            journal_name=project.name,
            profile_url="https://example.com/profil",
            journal=project,
        )
        body = mail.outbox[0].body
        assert "du projet" in body
        assert "de la revue" not in body

    def test_defaults_to_revue_wording_without_journal(self):
        send_reviewer_added(
            email="relecteur@example.com",
            reviewer_name="Jean Dupont",
            journal_name="Une revue",
            profile_url="https://example.com/profil",
        )
        body = mail.outbox[0].body
        assert "de la revue" in body
