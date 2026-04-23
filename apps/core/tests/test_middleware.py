import pytest
from django.test import RequestFactory

from apps.core.middleware import CurrentJournalMiddleware


@pytest.fixture
def get_response():
    return lambda request: None


@pytest.fixture
def middleware(get_response):
    return CurrentJournalMiddleware(get_response)


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.mark.django_db
class TestCurrentJournalMiddleware:
    def test_journal_set_on_journal_url(self, middleware, factory, journal):
        request = factory.get(f"/revues/{journal.slug}/")
        middleware(request)
        assert request.journal == journal

    def test_journal_none_on_home(self, middleware, factory):
        request = factory.get("/")
        middleware(request)
        # URLs sans slug → None directement (pas de SimpleLazyObject)
        assert request.journal is None

    def test_journal_none_on_admin(self, middleware, factory):
        request = factory.get("/admin/")
        middleware(request)
        assert request.journal is None

    def test_journal_none_on_unknown_slug(self, middleware, factory):
        request = factory.get("/revues/slug-inexistant/")
        middleware(request)
        # SlugLazyObject évalué → Journal introuvable → None
        assert not request.journal

    def test_journal_set_on_journal_subpath(self, middleware, factory, journal):
        request = factory.get(f"/revues/{journal.slug}/articles/")
        middleware(request)
        assert request.journal == journal
