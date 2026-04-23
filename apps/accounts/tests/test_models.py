import pytest

from apps.accounts.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email(self, user):
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"

    def test_no_required_fields_beyond_email(self):
        assert User.REQUIRED_FIELDS == []

    def test_str_representation(self, user):
        assert "test@example.com" in str(user)
        assert "Test" in str(user)

    def test_email_uniqueness(self, user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            User.objects.create_user(email="test@example.com", password="other")

    def test_create_superuser(self, db):
        su = User.objects.create_superuser(email="admin@example.com", password="adminpass")
        assert su.is_staff
        assert su.is_superuser
