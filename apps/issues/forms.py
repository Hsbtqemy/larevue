from django import forms

from apps.issues.models import Issue


class IssueEditForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["number", "thematic_title", "editor_name", "planned_publication_date", "description"]
        widgets = {
            "planned_publication_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }
