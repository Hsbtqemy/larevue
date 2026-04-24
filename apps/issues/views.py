from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.articles.models import Article, InternalNote
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.views import JournalOwnedPatchView, JournalOwnedTransitionView, compute_transitions
from apps.issues.forms import IssueEditForm
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


def _check_can_send_to_publisher(issue):
    agg = issue.articles.aggregate(
        total=Count("id"),
        validated=Count("id", filter=Q(state=Article.State.VALIDATED)),
    )
    total, validated = agg["total"], agg["validated"]
    if total == 0:
        return False, "Le numéro doit contenir au moins un article avant l'envoi."
    if validated < total:
        return False, f"{validated}/{total} articles validés. Tous doivent être validés avant l'envoi à l'éditeur."
    return True, ""


_ISSUE_TRANSITIONS = {
    "accept": {
        "label": "Accepter le projet",
        "description": "Le projet passe en statut Accepté.",
        "audit_verb": "a accepté le projet",
        "ui_group": "primary",
        "ui_variant": "primary",
        "is_danger": False,
    },
    "refuse": {
        "label": "Refuser le projet",
        "description": "Le projet sera définitivement refusé.",
        "audit_verb": "a refusé le projet",
        "ui_group": "secondary",
        "ui_variant": "danger-ghost",
        "is_danger": True,
    },
    "start_production": {
        "label": "Démarrer la production",
        "description": "Le numéro entre en phase de production éditoriale.",
        "audit_verb": "a démarré la production",
        "ui_group": "primary",
        "ui_variant": "primary",
        "is_danger": False,
    },
    "reopen_for_review": {
        "label": "Remettre en évaluation",
        "description": "Le numéro repasse en évaluation.",
        "audit_verb": "a remis le numéro en évaluation",
        "ui_group": "advanced",
        "ui_variant": "ghost",
        "is_danger": False,
    },
    "send_to_publisher": {
        "label": "Envoyer à l'éditeur",
        "description": "Le numéro est transmis à l'éditeur.",
        "audit_verb": "a envoyé le numéro à l'éditeur",
        "precondition": _check_can_send_to_publisher,
        "ui_group": "primary",
        "ui_variant": "primary",
        "is_danger": False,
    },
    "pause_production": {
        "label": "Suspendre la production",
        "description": "Le numéro repasse en statut Accepté.",
        "audit_verb": "a suspendu la production",
        "ui_group": "advanced",
        "ui_variant": "ghost",
        "is_danger": False,
    },
    "mark_as_published": {
        "label": "Marquer comme publié",
        "description": "Le numéro passe dans les archives en lecture seule. L'action peut être annulée via « Dépublier » si nécessaire.",
        "audit_verb": "a marqué le numéro comme publié",
        "ui_group": "primary",
        "ui_variant": "primary",
        "is_danger": False,
    },
    "recall_from_publisher": {
        "label": "Rappeler de chez l'éditeur",
        "description": "Le numéro repasse en production.",
        "audit_verb": "a rappelé le numéro de chez l'éditeur",
        "ui_group": "advanced",
        "ui_variant": "ghost",
        "is_danger": False,
    },
    "unpublish": {
        "label": "Dépublier",
        "description": "Le numéro repasse à l'état « Envoyé à l'éditeur ».",
        "audit_verb": "a dépublié le numéro",
        "ui_group": "advanced",
        "ui_variant": "danger-ghost",
        "is_danger": True,
    },
}


class IssueDetailView(JournalMemberRequiredMixin, DetailView):
    model = Issue
    pk_url_kwarg = "issue_id"
    template_name = "issues/detail.html"

    def get_object(self, queryset=None):
        issue = super().get_object(queryset)
        if issue.journal_id != self.request.journal.id:
            raise Http404
        return issue

    @staticmethod
    def _compute_transitions(issue):
        return compute_transitions(_ISSUE_TRANSITIONS, issue)

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

        is_editable = issue.state not in Issue.ARCHIVED_STATES
        transition_url = reverse(
            "issues:transition",
            kwargs={"slug": journal.slug, "issue_id": issue.pk},
        )

        ctx.update({
            "journal": journal,
            "articles": articles,
            "is_editable": is_editable,
            "transitions": self._compute_transitions(issue),
            "transition_url": transition_url,
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
        if obj.state in Issue.ARCHIVED_STATES:
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
        if issue.state in Issue.ARCHIVED_STATES:
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
        if issue.state in Issue.ARCHIVED_STATES:
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

        if issue.state in Issue.ARCHIVED_STATES:
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


class IssueTransitionView(JournalOwnedTransitionView):
    model = Issue
    pk_url_kwarg = "issue_id"
    journal_field_path = "journal"
    TRANSITION_SPECS = _ISSUE_TRANSITIONS

    def create_audit_note(self, obj, user, message):
        InternalNote.objects.create(issue=obj, author=user, content=message, is_automatic=True)

    def get_success_url(self, obj):
        return reverse(
            "issues:detail",
            kwargs={"slug": self.request.journal.slug, "issue_id": obj.pk},
        )
