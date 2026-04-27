from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.journals.models import Journal

User = get_user_model()


class JournalCreateAdminForm(forms.ModelForm):
    class Meta:
        model = Journal
        fields = ["name", "slug", "description", "accent_color"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))
        if Journal.objects.filter(slug=slug).exists():
            raise forms.ValidationError("Cet identifiant URL est déjà utilisé.")
        return slug


class UserCreateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "is_superuser"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte avec cet email existe déjà.")
        return email


class UserQuickCreateForm(forms.ModelForm):
    """Lightweight form for creating a user directly from a journal's member page."""

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte avec cet email existe déjà.")
        return email
