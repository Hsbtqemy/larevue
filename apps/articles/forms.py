import datetime

from django import forms

from apps.articles.models import Article
from apps.contacts.models import Contact
from apps.reviews.models import ReviewRequest


class ArticleEditForm(forms.ModelForm):
    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        if journal is not None:
            self.fields["author"].queryset = journal.contacts.order_by("last_name", "first_name")
        self.fields["author"].required = False

    class Meta:
        model = Article
        fields = ["title", "author", "article_type"]


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
        if journal:
            self.fields["reviewer"].queryset = journal.contacts.filter(
                usual_roles__overlap=[
                    Contact.Role.INTERNAL_REVIEWER,
                    Contact.Role.EXTERNAL_REVIEWER,
                ]
            ).order_by("last_name", "first_name")
        if article:
            qs = article.versions.order_by("-version_number")
            self.fields["article_version"].queryset = qs
            latest = qs.first()
            if latest:
                self.fields["article_version"].initial = latest.pk
        self.fields["deadline"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["deadline"].initial = datetime.date.today() + datetime.timedelta(days=28)

    class Meta:
        model = ReviewRequest
        fields = ["reviewer", "article_version", "deadline"]
        labels = {"article_version": "Version à relire"}


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
