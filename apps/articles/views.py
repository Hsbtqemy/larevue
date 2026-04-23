from django.db.models import Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.articles.forms import ArticleEditForm
from apps.articles.models import Article, InternalNote
from apps.contacts.models import Contact
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.views import JournalOwnedPatchView
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


class _ArticleJournalMixin(JournalOwnedObjectMixin):
    model = Article
    pk_url_kwarg = "article_id"
    journal_field_path = "issue__journal"

    def get_object_or_404(self):
        try:
            return Article.objects.select_related("issue").get(
                pk=self.kwargs["article_id"],
                issue_id=self.kwargs["issue_id"],
                issue__journal=self.request.journal,
            )
        except Article.DoesNotExist:
            raise Http404

    def _check_archived(self, article):
        if article.issue.state in Issue.ARCHIVED_STATES:
            return JsonResponse({"error": "Cet article ne peut plus être modifié."}, status=403)
        return None


class ArticleDetailView(JournalMemberRequiredMixin, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "articles/detail.html"

    def get_queryset(self):
        return Article.objects.select_related(
            "issue", "issue__journal", "author"
        ).prefetch_related(
            "versions",
            "review_requests",
            Prefetch(
                "internal_notes",
                queryset=InternalNote.objects.order_by("-created_at").select_related("author"),
            ),
        )

    def get_object(self, queryset=None):
        article = super().get_object(queryset)
        if article.issue.journal_id != self.request.journal.id:
            raise Http404
        if article.issue_id != self.kwargs["issue_id"]:
            raise Http404
        return article

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        article = self.object
        issue = article.issue
        journal = self.request.journal

        versions = list(article.versions.all())
        review_requests = list(article.review_requests.all())
        reviews_received = sum(
            1 for rr in review_requests if rr.state == ReviewRequest.State.RECEIVED
        )

        internal_notes = list(article.internal_notes.all())

        author_options = [
            (c.pk, c.full_name)
            for c in journal.contacts.order_by("last_name", "first_name")
        ]
        if article.author and (article.author_id, article.author.full_name) not in author_options:
            author_options = [(article.author_id, article.author.full_name)] + author_options

        is_archived = issue.state in Issue.ARCHIVED_STATES
        latest_version_number = versions[-1].version_number if versions else None

        ctx.update({
            "issue": issue,
            "journal": journal,
            "internal_notes": internal_notes,
            "author_options": author_options,
            "is_archived": is_archived,
            "version_count": len(versions),
            "review_request_count": len(review_requests),
            "reviews_received": reviews_received,
            "latest_version_number": latest_version_number,
            "article_count_in_issue": issue.articles.count(),
            "user_journal_count": self.request.user.memberships.count(),
        })
        return ctx


class ArticlePatchView(_ArticleJournalMixin, JournalOwnedPatchView):
    ALLOWED_FIELDS = {"title", "author", "author_name_override", "article_type"}
    AUDIT_FIELDS = {"title", "author", "article_type"}
    FULL_CLEAN_EXCLUDE = ["state"]

    def check_editable(self, obj):
        return self._check_archived(obj)

    def resolve_field_value(self, field_name, raw_value, field_obj):
        if field_name == "author":
            if not raw_value:
                return None
            try:
                return Contact.objects.get(pk=int(raw_value), journal=self.request.journal)
            except (Contact.DoesNotExist, ValueError):
                raise ValueError("Contact introuvable.")
        return super().resolve_field_value(field_name, raw_value, field_obj)

    def create_audit_note(self, obj, field_name, old_value, new_value, field_obj):
        InternalNote.objects.create(
            article=obj,
            author=self.request.user,
            content=f"{field_obj.verbose_name} modifié·e : « {old_value} » → « {new_value} »",
            is_automatic=True,
        )


class ArticleEditView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        form = ArticleEditForm(request.POST, instance=article, journal=request.journal)
        if form.is_valid():
            form.save()
            url = reverse(
                "articles:detail",
                kwargs={
                    "slug": request.journal.slug,
                    "issue_id": issue_id,
                    "article_id": article_id,
                },
            )
            return JsonResponse({"redirect_url": url})

        errors = {
            field: [str(e.message) for e in errs]
            for field, errs in form.errors.as_data().items()
        }
        return JsonResponse({"errors": errors}, status=400)


class ArticleDeleteView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def delete(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        article.delete()
        url = reverse(
            "issues:detail",
            kwargs={"slug": request.journal.slug, "issue_id": issue_id},
        )
        return JsonResponse({"redirect_url": url})


class ArticleNoteCreateView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        content = request.POST.get("content", "").strip()
        if not content:
            return JsonResponse({"error": "Le contenu ne peut pas être vide."}, status=400)

        note = InternalNote.objects.create(
            article=article,
            author=request.user,
            content=content,
            is_automatic=False,
        )
        return render(request, "articles/_note.html", {"note": note})
