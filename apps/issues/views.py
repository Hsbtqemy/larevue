from django.http import Http404, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.articles.models import Article, InternalNote
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.views import JournalOwnedPatchView
from apps.issues.forms import IssueEditForm
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest

_ARCHIVED_STATES = frozenset({Issue.State.PUBLISHED, Issue.State.REFUSED})


class IssueDetailView(JournalMemberRequiredMixin, DetailView):
    model = Issue
    pk_url_kwarg = "issue_id"
    template_name = "issues/detail.html"

    def get_object(self, queryset=None):
        issue = super().get_object(queryset)
        if issue.journal_id != self.request.journal.id:
            raise Http404
        return issue

    def _primary_action(self, issue, articles):
        state = issue.state
        if state == Issue.State.UNDER_REVIEW:
            return {"type": "review"}
        if state in (Issue.State.ACCEPTED, Issue.State.IN_PRODUCTION):
            all_validated = bool(articles) and all(
                a.state == Article.State.VALIDATED for a in articles
            )
            return {"type": "send", "enabled": all_validated}
        if state == Issue.State.SENT_TO_PUBLISHER:
            return {"type": "publish"}
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        issue = self.object
        journal = self.request.journal

        articles = list(
            issue.articles
            .prefetch_related("versions", "review_requests")
            .order_by("order", "created_at")
        )
        for a in articles:
            versions = list(a.versions.all())
            a.latest_version = versions[-1] if versions else None
            rrs = list(a.review_requests.all())
            a.reviews_received = sum(1 for r in rrs if r.state == ReviewRequest.State.RECEIVED)
            a.reviews_total = len(rrs)

        member_names = [
            m.user.get_full_name() or m.user.email
            for m in journal.memberships.select_related("user").all()
        ]
        if issue.editor_name and issue.editor_name not in member_names:
            member_names = [issue.editor_name] + member_names

        is_editable = issue.state not in _ARCHIVED_STATES

        ctx.update({
            "journal": journal,
            "articles": articles,
            "is_editable": is_editable,
            "primary_action": self._primary_action(issue, articles),
            "member_names": member_names,
            "user_journal_count": self.request.user.memberships.count(),
        })
        return ctx


class IssuePatchView(JournalOwnedPatchView):
    model = Issue
    pk_url_kwarg = "issue_id"
    ALLOWED_FIELDS = {"number", "thematic_title", "editor_name", "planned_publication_date", "description"}
    AUDIT_FIELDS = {"number", "thematic_title", "editor_name", "planned_publication_date", "description"}
    FULL_CLEAN_EXCLUDE = ["state", "cover_image", "final_pdf"]

    def check_editable(self, obj):
        if obj.state in _ARCHIVED_STATES:
            return JsonResponse({"error": "Ce numéro ne peut plus être modifié."}, status=403)
        return None

    def create_audit_note(self, obj, field_name, old_value, new_value, field_obj):
        InternalNote.objects.create(
            issue=obj,
            author=self.request.user,
            content=f"{field_obj.verbose_name} modifié·e : « {old_value} » → « {new_value} »",
            is_automatic=True,
        )


class IssueImageUploadView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Issue
    pk_url_kwarg = "issue_id"

    def post(self, request, issue_id, **kwargs):
        issue = self.get_object_or_404()
        if issue.state in _ARCHIVED_STATES:
            return JsonResponse({"error": "Ce numéro ne peut plus être modifié."}, status=403)

        file = request.FILES.get("cover_image")
        if not file:
            return JsonResponse({"error": "Aucun fichier reçu."}, status=400)

        issue.cover_image = file
        try:
            issue.full_clean(exclude=["state", "final_pdf"])
            issue.save(update_fields=["cover_image"])
        except ValidationError as e:
            return JsonResponse({"error": " ".join(e.messages)}, status=400)

        return JsonResponse({"url": issue.cover_image.url})

    def patch(self, request, issue_id, **kwargs):
        issue = self.get_object_or_404()
        if issue.state in _ARCHIVED_STATES:
            return JsonResponse({"error": "Ce numéro ne peut plus être modifié."}, status=403)

        if issue.cover_image:
            issue.cover_image.delete(save=False)
        issue.cover_image = None
        issue.save(update_fields=["cover_image"])
        return JsonResponse({"ok": True})


class IssueEditView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Issue
    pk_url_kwarg = "issue_id"

    def post(self, request, issue_id, **kwargs):
        issue = self.get_object_or_404()

        if issue.state in _ARCHIVED_STATES:
            return JsonResponse({"error": "Ce numéro ne peut plus être modifié."}, status=403)

        form = IssueEditForm(request.POST, instance=issue)
        if form.is_valid():
            form.save()
            url = reverse(
                "issues:detail",
                kwargs={"slug": request.journal.slug, "issue_id": issue_id},
            )
            return JsonResponse({"redirect_url": url})

        errors = {
            field: [str(e.message) for e in errs]
            for field, errs in form.errors.as_data().items()
        }
        return JsonResponse({"errors": errors}, status=400)


class IssueDeleteView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Issue
    pk_url_kwarg = "issue_id"

    def delete(self, request, issue_id, **kwargs):
        issue = self.get_object_or_404()
        issue.delete()
        url = reverse("journal_dashboard", kwargs={"slug": request.journal.slug})
        return JsonResponse({"redirect_url": url})
