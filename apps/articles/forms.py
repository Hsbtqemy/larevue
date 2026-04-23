from django import forms

from apps.articles.models import Article


class ArticleEditForm(forms.ModelForm):
    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        if journal is not None:
            self.fields["author"].queryset = journal.contacts.order_by("last_name", "first_name")
        self.fields["author"].required = False

    class Meta:
        model = Article
        fields = ["title", "author", "article_type"]
