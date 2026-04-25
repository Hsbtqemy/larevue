from django import forms


class ProfilePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput,
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

    def clean_current_password(self):
        pw = self.cleaned_data["current_password"]
        if not self._user.check_password(pw):
            raise forms.ValidationError("Mot de passe incorrect.")
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("new_password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password_confirm", "Les deux mots de passe ne correspondent pas.")
        return cleaned
