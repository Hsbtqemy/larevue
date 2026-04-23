import pytest

from apps.journals.models import Journal


@pytest.mark.django_db
class TestTimestampedModel:
    def test_created_at_set_on_creation(self, journal):
        assert journal.created_at is not None

    def test_updated_at_changes_on_save(self, journal):
        original = journal.updated_at
        journal.description = "modifié"
        journal.save()
        journal.refresh_from_db()
        assert journal.updated_at > original


@pytest.mark.django_db
class TestSoftDeleteModel:
    def test_soft_delete_hides_from_default_manager(self, journal):
        pk = journal.pk
        journal.delete()
        assert Journal.objects.filter(pk=pk).count() == 0

    def test_soft_delete_preserved_in_all_objects(self, journal):
        pk = journal.pk
        journal.delete()
        assert Journal.all_objects.filter(pk=pk).count() == 1

    def test_is_deleted_property(self, journal):
        assert not journal.is_deleted
        journal.delete()
        assert journal.is_deleted

    def test_restore(self, journal):
        pk = journal.pk
        journal.delete()
        journal.restore()
        assert Journal.objects.filter(pk=pk).count() == 1
        assert journal.deleted_at is None

    def test_hard_delete_removes_record(self, journal):
        pk = journal.pk
        journal.hard_delete()
        assert Journal.all_objects.filter(pk=pk).count() == 0
