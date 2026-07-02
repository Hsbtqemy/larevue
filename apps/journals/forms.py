from django import forms

from apps.core.utils import MAX_UPLOAD_MB
from apps.journals.models import Journal, JournalDocument


class JournalEditForm(forms.ModelForm):
    class Meta:
        model = Journal
        fields = [
            "name", "accent_color", "description", "logo",
            "directors", "publisher", "issn_print", "issn_online",
            "periodicity", "founded_year", "website",
            "email_sender_name", "email_intro", "auto_reminder_days",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "email_intro": forms.Textarea(attrs={"rows": 3}),
        }


class PersonalProjectCreateForm(forms.ModelForm):
    """Création en libre-service d'un projet ponctuel (livre, actes de colloque).

    Volontairement dépourvu des champs institutionnels d'une revue périodique
    (ISSN, périodicité, éditeur...) — non pertinents pour un projet à numéro unique.
    """

    class Meta:
        model = Journal
        fields = ["name", "description"]
        labels = {
            "name": "Titre du projet",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class JournalDocumentForm(forms.ModelForm):
    class Meta:
        model = JournalDocument
        fields = ["name", "description", "file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and f.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Le fichier dépasse la taille maximale autorisée ({MAX_UPLOAD_MB} Mo)."
            )
        return f
