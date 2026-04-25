from django import forms

from apps.contacts.models import Contact


class ContactCreateForm(forms.ModelForm):
    usual_roles = forms.MultipleChoiceField(
        choices=Contact.Role.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Rôles habituels",
    )

    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "affiliation", "usual_roles", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


ContactEditForm = ContactCreateForm
