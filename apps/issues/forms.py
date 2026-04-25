from django import forms

from apps.core.utils import MAX_UPLOAD_MB
from apps.issues.models import Issue, IssueDocument


class IssueEditForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["number", "thematic_title", "editor_name", "planned_publication_date", "description"]
        widgets = {
            "planned_publication_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class IssueCreateForm(forms.ModelForm):
    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = Issue
        fields = [
            "number", "thematic_title", "description", "editor_name",
            "planned_publication_date", "deadline_articles",
        ]
        widgets = {
            "planned_publication_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "deadline_articles": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class IssueDocumentForm(forms.ModelForm):
    class Meta:
        model = IssueDocument
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
