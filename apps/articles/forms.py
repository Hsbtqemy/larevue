import datetime

from django import forms

from apps.articles.models import Article
from apps.contacts.models import Contact
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


class ArticleEditForm(forms.ModelForm):
    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = Article
        fields = ["title", "article_type"]


class ArticleCreateForm(forms.ModelForm):
    file = forms.FileField(label="Fichier (facultatif)", required=False)

    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "file":
                continue
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("class", "text-input")

    class Meta:
        model = Article
        fields = ["title", "article_type", "abstract"]
        widgets = {"abstract": forms.Textarea(attrs={"rows": 4})}


class ArticleCreateWithIssueForm(ArticleCreateForm):
    issue = forms.ModelChoiceField(
        queryset=Issue.objects.none(),
        label="Numéro",
        empty_label="— Choisir un numéro —",
    )

    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, journal=journal, **kwargs)
        if journal is not None:
            self.fields["issue"].queryset = journal.issues.filter(
                state__in=Issue.ACTIVE_STATES
            ).order_by("-number")
        self.fields["issue"].widget.attrs.setdefault("class", "text-input")


class ArticleVersionUploadForm(forms.Form):
    file = forms.FileField(label="Fichier")
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Commentaire",
    )


class ReviewRequestCreateForm(forms.ModelForm):
    def __init__(self, *args, journal=None, article=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["deadline"].initial = datetime.date.today() + datetime.timedelta(days=28)

    class Meta:
        model = ReviewRequest
        fields = ["deadline"]


class ReviewRequestReceiveForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["verdict"].required = True
        self.fields["received_file"].required = False
        self.fields["internal_notes"].required = False

    class Meta:
        model = ReviewRequest
        fields = ["verdict", "received_file", "internal_notes"]
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 3})}
