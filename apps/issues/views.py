import datetime

from django.core.exceptions import ValidationError
from django.db.models import Count, F
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.articles.models import Article, InternalNote
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.views import JournalOwnedCreateView, JournalOwnedPatchView, JournalOwnedTransitionView, compute_transitions
from apps.issues.forms import IssueCreateForm, IssueEditForm
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


def _check_has_articles(issue):
    if issue.articles.count() == 0:
        return False, "Le numéro doit contenir au moins un article."
    return True, ""


_ISSUE_TRANSITIONS = {
    # ── Flux normal ───────────────────────────────────────────────────
    "accept": {
        "label": "Accepter le projet",
        "description": "Le projet est accepté. Le numéro entre en préparation, en attente des articles.",
        "audit_verb": "a accepté le projet",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "refuse": {
        "label": "Refuser le projet",
        "description": "Le projet sera définitivement refusé.",
        "audit_verb": "a refusé le projet",
        "ui_group": "primary",
        "ui_variant": "danger-ghost",
    },
    "send_to_reviewers": {
        "label": "Envoyer aux relecteurs",
        "description": "Le numéro entre en phase de relecture.",
        "audit_verb": "a envoyé le numéro aux relecteurs",
        "precondition": _check_has_articles,
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "reviews_received_return_to_authors": {
        "label": "Relectures reçues — renvoyer aux auteurs",
        "description": "Les relectures ont été reçues. Le numéro passe en phase de révision auteur.",
        "audit_verb": "a renvoyé le numéro aux auteurs pour révision",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "v2_received_final_check": {
        "label": "V2 reçues — passer en vérification finale",
        "description": "Les versions révisées ont été reçues. Le numéro entre en vérification finale.",
        "audit_verb": "a lancé la vérification finale",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "send_to_publisher": {
        "label": "Envoyer à l'éditeur",
        "description": "Le numéro est transmis à l'éditeur.",
        "audit_verb": "a envoyé le numéro à l'éditeur",
        "precondition": _check_has_articles,
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "mark_as_published": {
        "label": "Marquer comme publié",
        "description": "Le numéro passe dans les archives en lecture seule. L'action peut être annulée via « Dépublier » si nécessaire.",
        "audit_verb": "a marqué le numéro comme publié",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    # ── Rollbacks ─────────────────────────────────────────────────────
    "reopen_for_review": {
        "label": "Remettre en évaluation",
        "description": "Le numéro repasse en évaluation.",
        "audit_verb": "a remis le numéro en évaluation",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "recall_reviewers": {
        "label": "Annuler l'envoi aux relecteurs",
        "description": "Le numéro repasse en statut Accepté.",
        "audit_verb": "a annulé l'envoi aux relecteurs",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "recall_to_authors": {
        "label": "Annuler l'envoi aux auteurs",
        "description": "Le numéro repasse en phase de relecture.",
        "audit_verb": "a annulé l'envoi aux auteurs",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "reopen_revision": {
        "label": "Retour en phase révision",
        "description": "Le numéro repasse en phase de révision auteur.",
        "audit_verb": "a rouvert la phase de révision",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "recall_final_check": {
        "label": "Rappeler de chez l'éditeur",
        "description": "Le numéro repasse en vérification finale.",
        "audit_verb": "a rappelé le numéro de chez l'éditeur",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "unpublish": {
        "label": "Dépublier",
        "description": "Le numéro repasse à l'état « Envoyé à l'éditeur ».",
        "audit_verb": "a dépublié le numéro",
        "ui_group": "advanced",
        "ui_variant": "danger-ghost",
    },
}


_TIMELINE_STATES = [
    Issue.State.UNDER_REVIEW,
    Issue.State.ACCEPTED,
    Issue.State.IN_REVIEW,
    Issue.State.IN_REVISION,
    Issue.State.FINAL_CHECK,
    Issue.State.SENT_TO_PUBLISHER,
    Issue.State.PUBLISHED,
]

_STATE_DEADLINE_FIELD = {
    Issue.State.IN_REVIEW: "deadline_articles",
    Issue.State.IN_REVISION: "deadline_reviews",
    Issue.State.FINAL_CHECK: "deadline_v2",
    Issue.State.SENT_TO_PUBLISHER: "deadline_final_check",
    Issue.State.PUBLISHED: "deadline_sent_to_publisher",
}


def _build_timeline(issue):
    today = datetime.date.today()
    n = len(_TIMELINE_STATES)
    try:
        current_idx = _TIMELINE_STATES.index(issue.state)
    except ValueError:
        current_idx = -1

    milestones = []
    for i, state in enumerate(_TIMELINE_STATES):
        deadline_field = _STATE_DEADLINE_FIELD.get(state)
        deadline = getattr(issue, deadline_field) if deadline_field else None
        if deadline is None and state == Issue.State.PUBLISHED:
            deadline = issue.planned_publication_date
        is_done = current_idx > i
        is_current = current_idx == i
        milestones.append({
            "state": state,
            "label": state.label,
            "is_current": is_current,
            "is_done": is_done,
            "deadline": deadline,
            "is_late": bool(deadline and deadline < today and not is_done and not (issue.state in Issue.ARCHIVED_STATES and is_current)),
            "position_pct": round(i / (n - 1) * 100),
        })
    return milestones


class IssueListView(JournalMemberRequiredMixin, TemplateView):
    template_name = "issues/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        journal = self.request.journal
        tab = self.request.GET.get("tab", "active")

        active_qs = journal.issues.filter(state__in=Issue.ACTIVE_STATES).order_by(
            F("planned_publication_date").asc(nulls_last=True)
        )
        archived_qs = journal.issues.filter(state__in=Issue.ARCHIVED_STATES).order_by(
            F("planned_publication_date").desc(nulls_last=True)
        )

        ctx.update({
            "journal": journal,
            "tab": tab,
            "active_issues": active_qs,
            "archived_issues": archived_qs,
            "active_count": active_qs.count(),
            "archived_count": archived_qs.count(),
            "user_journal_count": self.request.user.memberships.count(),
        })
        return ctx


class IssueCreateView(JournalOwnedCreateView):
    form_class = IssueCreateForm
    template_name = "issues/create.html"

    def get_success_url(self, instance):
        return reverse(
            "issues:detail",
            kwargs={"slug": self.request.journal.slug, "issue_id": instance.pk},
        )


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
            "timeline": _build_timeline(issue),
        })
        return ctx


class IssuePatchView(JournalOwnedPatchView):
    model = Issue
    pk_url_kwarg = "issue_id"
    ALLOWED_FIELDS = {
        "number", "thematic_title", "editor_name", "planned_publication_date", "description",
        "deadline_articles", "deadline_reviews", "deadline_v2",
        "deadline_final_check", "deadline_sent_to_publisher",
    }
    AUDIT_FIELDS = ALLOWED_FIELDS
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
