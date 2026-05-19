from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.reviews.models import ReviewRequest


class ProfilePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput,
        required=False,
    )
    new_password = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput,
        min_length=8,
    )
    new_password_confirm = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput,
    )

    def __init__(self, user, *args, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)
        if not user.must_change_password:
            self.fields["current_password"].required = True

    def clean_current_password(self):
        pw = self.cleaned_data.get("current_password", "")
        if not pw:
            return pw
        if not self._user.check_password(pw):
            raise forms.ValidationError("Mot de passe incorrect.")
        return pw

    def clean(self):
        cleaned = super().clean()
        if not self._user.must_change_password and not cleaned.get("current_password"):
            self.add_error("current_password", "Ce champ est obligatoire.")
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("new_password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password_confirm", "Les deux mots de passe ne correspondent pas.")
        return cleaned


class ReviewerInviteForm(forms.Form):
    email = forms.EmailField(label="Adresse e-mail")
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)


class ReviewerActivateForm(forms.Form):
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput,
    )

    def clean_password(self):
        pw = self.cleaned_data["password"]
        validate_password(pw)
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", "Les deux mots de passe ne correspondent pas.")
        return cleaned


class ReviewerSubmitForm(forms.Form):
    received_file = forms.FileField(
        label="Fichier de relecture",
        help_text="Format PDF ou Word accepté.",
    )
    verdict = forms.ChoiceField(
        label="Verdict",
        choices=ReviewRequest.Verdict.choices,
    )
