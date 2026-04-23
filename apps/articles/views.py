from django.http import Http404
from django.views.generic import DetailView

from apps.articles.models import Article
from apps.core.mixins import JournalMemberRequiredMixin


class ArticleDetailView(JournalMemberRequiredMixin, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "articles/detail.html"

    def get_queryset(self):
        return Article.objects.select_related("issue")

    def get_object(self, queryset=None):
        article = super().get_object(queryset)
        if article.issue.journal_id != self.request.journal.id:
            raise Http404
        return article

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["journal"] = self.request.journal
        return ctx
