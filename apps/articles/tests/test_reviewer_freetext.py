import datetime

import pytest
from django.urls import reverse

from apps.reviews.models import ReviewRequest


def _review_create_url(journal, issue, article):
    return reverse(
        "articles:review_create",
        kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
    )


def _base_data(version, **overrides):
    deadline = (datetime.date.today() + datetime.timedelta(days=28)).isoformat()
    data = {"article_version": version.pk, "deadline": deadline}
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestReviewerFreetext:
    def test_create_with_contact_reviewer(
        self, client, user, membership, journal, issue, article, article_version, contact
    ):
        client.force_login(user)
        res = client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id=contact.pk,
            reviewer_name=contact.full_name,
        ))
        assert res.status_code == 200
        rr = ReviewRequest.objects.get(article=article)
        assert rr.reviewer == contact
        assert rr.reviewer_name_snapshot == contact.full_name

    def test_create_with_freetext_reviewer(
        self, client, user, membership, journal, issue, article, article_version
    ):
        client.force_login(user)
        res = client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id="",
            reviewer_name="Relecteur Externe",
        ))
        assert res.status_code == 200
        rr = ReviewRequest.objects.get(article=article)
        assert rr.reviewer is None
        assert rr.reviewer_name_snapshot == "Relecteur Externe"

    def test_freetext_audit_log_uses_name(
        self, client, user, membership, journal, issue, article, article_version
    ):
        from apps.articles.models import InternalNote
        client.force_login(user)
        client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id="",
            reviewer_name="Nom Libre",
        ))
        note = InternalNote.objects.get(article=article, is_automatic=True)
        assert "Nom Libre" in note.content

    def test_missing_reviewer_name_returns_400(
        self, client, user, membership, journal, issue, article, article_version
    ):
        client.force_login(user)
        res = client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id="",
            reviewer_name="",
        ))
        assert res.status_code == 400

    def test_invalid_reviewer_id_returns_400(
        self, client, user, membership, journal, issue, article, article_version
    ):
        client.force_login(user)
        res = client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id="99999",
            reviewer_name="Fallback",
        ))
        assert res.status_code == 400

    def test_other_journal_reviewer_id_returns_400(
        self, client, user, membership, journal, issue, article, article_version, db
    ):
        from apps.contacts.models import Contact
        from apps.journals.models import Journal

        other = Journal.objects.create(name="Autre", slug="autre-rv-ft")
        other_contact = Contact.objects.create(journal=other, first_name="A", last_name="B")
        client.force_login(user)
        res = client.post(_review_create_url(journal, issue, article), _base_data(
            article_version,
            reviewer_id=other_contact.pk,
            reviewer_name="A B",
        ))
        assert res.status_code == 400
