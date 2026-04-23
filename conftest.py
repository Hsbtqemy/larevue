import pytest

from apps.accounts.models import User
from apps.contacts.models import Contact
from apps.issues.models import Issue
from apps.journals.models import Journal, Membership


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        password="testpass123",
    )


@pytest.fixture
def journal(db):
    return Journal.objects.create(name="Revue de test", slug="revue-de-test")


@pytest.fixture
def membership(db, user, journal):
    return Membership.objects.create(user=user, journal=journal)


@pytest.fixture
def issue(db, journal):
    return Issue.objects.create(
        journal=journal,
        number="1",
        thematic_title="Numéro de test",
        editor_name="Éditeur Test",
    )


@pytest.fixture
def contact(db, journal):
    return Contact.objects.create(
        journal=journal,
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
    )


@pytest.fixture
def article(db, issue, contact):
    from apps.articles.models import Article

    return Article.objects.create(issue=issue, title="Article de test", author=contact)
