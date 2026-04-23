import pytest
from django.db import IntegrityError

from apps.journals.models import Journal, Membership


@pytest.mark.django_db
class TestJournal:
    def test_slug_auto_generated(self, db):
        j = Journal.objects.create(name="Revue d'Histoire")
        assert j.slug == "revue-dhistoire"

    def test_slug_not_overwritten_if_provided(self, db):
        j = Journal.objects.create(name="Revue X", slug="mon-slug-custom")
        assert j.slug == "mon-slug-custom"

    def test_name_uniqueness(self, journal):
        with pytest.raises(IntegrityError):
            Journal.objects.create(name=journal.name)

    def test_str(self, journal):
        assert str(journal) == "Revue de test"


@pytest.mark.django_db
class TestMembership:
    def test_membership_created(self, membership):
        assert membership.user is not None
        assert membership.journal is not None

    def test_unique_constraint(self, membership):
        with pytest.raises(IntegrityError):
            Membership.objects.create(user=membership.user, journal=membership.journal)
