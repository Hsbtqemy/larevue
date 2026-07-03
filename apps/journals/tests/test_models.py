import pytest
from django.db import IntegrityError

from apps.issues.models import Issue
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

    def test_slug_auto_suffixed_on_collision(self, db):
        """Deux noms distincts peuvent produire le même slug (accents, casse)."""
        j1 = Journal.objects.create(name="Café 2026")
        j2 = Journal.objects.create(name="Cafe 2026")
        assert j1.slug == "cafe-2026"
        assert j2.slug == "cafe-2026-2"

    def test_slug_auto_suffixed_skips_taken_suffixes(self, db):
        Journal.objects.create(name="Autre 1", slug="cafe-2026")
        Journal.objects.create(name="Autre 2", slug="cafe-2026-2")
        j3 = Journal.objects.create(name="Cafe 2026")
        assert j3.slug == "cafe-2026-3"

    def test_str(self, journal):
        assert str(journal) == "Revue de test"

    def test_standalone_status_none_for_periodical(self, journal, issue):
        assert journal.standalone_status is None

    def test_standalone_status_returns_sole_issue(self, db):
        project = Journal.objects.create(name="Mon projet", kind=Journal.Kind.STANDALONE)
        issue = Issue.objects.create(
            journal=project, number="1", thematic_title="Mon livre", editor_name="Moi",
        )
        assert project.standalone_status == issue

    def test_standalone_status_none_without_issue(self, db):
        project = Journal.objects.create(name="Mon projet", kind=Journal.Kind.STANDALONE)
        assert project.standalone_status is None

    def test_standalone_status_none_with_multiple_issues(self, db):
        project = Journal.objects.create(name="Mon projet", kind=Journal.Kind.STANDALONE)
        Issue.objects.create(
            journal=project, number="1", thematic_title="Tome 1", editor_name="Moi",
        )
        Issue.objects.create(
            journal=project, number="2", thematic_title="Tome 2", editor_name="Moi",
        )
        assert project.standalone_status is None


@pytest.mark.django_db
class TestMembership:
    def test_membership_created(self, membership):
        assert membership.user is not None
        assert membership.journal is not None

    def test_unique_constraint(self, membership):
        with pytest.raises(IntegrityError):
            Membership.objects.create(user=membership.user, journal=membership.journal)
