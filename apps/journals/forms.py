from django import forms

from apps.journals.models import JournalDocument

MAX_UPLOAD_MB = 25


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
