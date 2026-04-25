from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView
from django_fsm import can_proceed

from apps.articles.forms import (
    ArticleCreateForm,
    ArticleCreateWithIssueForm,
    ArticleEditForm,
    ArticleVersionUploadForm,
    ReviewRequestCreateForm,
    ReviewRequestReceiveForm,
)
from apps.articles.models import Article, ArticleVersion, InternalNote
from apps.articles.utils import log_action, oob_counters_html
from apps.contacts.models import Contact
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.utils import file_response
from apps.core.views import JournalOwnedCreateView, JournalOwnedPatchView, JournalOwnedTransitionView, compute_transitions
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


def _check_article_archived(article):
    if article.issue.state in Issue.ARCHIVED_STATES:
        return JsonResponse({"error": "Cet article ne peut plus être modifié."}, status=403)
    return None


class ArticleCreateView(JournalOwnedCreateView):
    form_class = ArticleCreateForm
    template_name = "articles/create.html"

    def _get_issue(self):
        issue = get_object_or_404(Issue, pk=self.kwargs["issue_id"], journal=self.request.journal)
        if issue.state in Issue.ARCHIVED_STATES:
            raise PermissionDenied
        return issue

    def get(self, request, **kwargs):
        self.issue = self._get_issue()
        return super().get(request, **kwargs)

    def post(self, request, **kwargs):
        self.issue = self._get_issue()
        return super().post(request, **kwargs)

    def get_extra_context(self):
        return {"issue": self.issue}

    def prepare_instance(self, instance, form):
        instance.issue = self.issue

    def post_create(self, instance, form):
        f = form.cleaned_data.get("file")
        if f:
            instance.mark_received()
            instance.save()
            ArticleVersion.objects.create(article=instance, file=f, uploaded_by=self.request.user)

    def get_success_url(self, instance):
        return reverse(
            "issues:detail",
            kwargs={"slug": self.request.journal.slug, "issue_id": self.issue.pk},
        )


class ArticleCreateFromJournalView(JournalOwnedCreateView):
    form_class = ArticleCreateWithIssueForm
    template_name = "articles/create_from_journal.html"

    def _has_active_issues(self):
        return self.request.journal.issues.filter(state__in=Issue.ACTIVE_STATES).exists()

    def get(self, request, **kwargs):
        if not self._has_active_issues():
            messages.warning(request, "Créez d'abord un projet de numéro pour y importer des articles.")
            return redirect(reverse("issues:create", kwargs={"slug": request.journal.slug}))
        return super().get(request, **kwargs)

    def post(self, request, **kwargs):
        if not self._has_active_issues():
            messages.warning(request, "Créez d'abord un projet de numéro pour y importer des articles.")
            return redirect(reverse("issues:create", kwargs={"slug": request.journal.slug}))
        return super().post(request, **kwargs)

    def prepare_instance(self, instance, form):
        instance.issue = form.cleaned_data["issue"]

    def post_create(self, instance, form):
        f = form.cleaned_data.get("file")
        if f:
            instance.mark_received()
            instance.save()
            ArticleVersion.objects.create(article=instance, file=f, uploaded_by=self.request.user)

    def get_success_url(self, instance):
        return reverse(
            "issues:detail",
            kwargs={"slug": self.request.journal.slug, "issue_id": instance.issue_id},
        )


_ARTICLE_TRANSITIONS = {
    "send_to_review": {  # sourced from received OR revised — not from pending
        "label": "Envoyer en relecture",
        "description": "L'article passe en phase de relecture.",
        "description_fn": lambda a: (
            "Nouveau tour de relecture après révision auteur."
            if a.state == Article.State.REVISED
            else "L'article passe en phase de relecture."
        ),
        "audit_verb": "a envoyé l'article en relecture",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "cancel_review": {
        "label": "Annuler la relecture",
        "description": "L'article revient à l'état Reçu (annulation d'erreur de saisie).",
        "audit_verb": "a annulé la relecture",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
    "mark_reviews_received": {
        "label": "Clore la relecture",
        "description": "Toutes les relectures sont considérées reçues.",
        "audit_verb": "a clos la phase de relecture",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "send_to_author": {
        "label": "Retourner à l'auteur",
        "description": "L'article est renvoyé à l'auteur pour révisions.",
        "audit_verb": "a retourné l'article à l'auteur",
        "ui_group": "secondary",
        "ui_variant": "ghost",
    },
    "validate": {
        "label": "Valider l'article",
        "description": "L'article est validé pour publication.",
        "audit_verb": "a validé l'article",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "mark_as_revised": {
        "label": "Marquer comme révisé",
        "description": "La version révisée a été reçue.",
        "audit_verb": "a marqué l'article comme révisé",
        "ui_group": "primary",
        "ui_variant": "primary",
    },
    "request_more_revision": {
        "label": "Demander des corrections",
        "description": "L'article est renvoyé à l'auteur pour corrections supplémentaires.",
        "audit_verb": "a demandé des corrections supplémentaires",
        "ui_group": "advanced",
        "ui_variant": "ghost",
    },
}


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
        return _check_article_archived(article)


class _ReviewRequestMixin(JournalOwnedObjectMixin):
    model = ReviewRequest
    pk_url_kwarg = "review_id"
    journal_field_path = "article__issue__journal"

    def get_object_or_404(self):
        try:
            return ReviewRequest.objects.select_related(
                "article__issue", "reviewer", "article_version"
            ).get(
                pk=self.kwargs["review_id"],
                article_id=self.kwargs["article_id"],
                article__issue_id=self.kwargs["issue_id"],
                article__issue__journal=self.request.journal,
            )
        except ReviewRequest.DoesNotExist:
            raise Http404

    def _check_archived(self, article):
        return _check_article_archived(article)


class ArticleDetailView(JournalMemberRequiredMixin, DetailView):
    model = Article
    pk_url_kwarg = "article_id"
    template_name = "articles/detail.html"

    def get_queryset(self):
        return Article.objects.select_related(
            "issue", "issue__journal", "author"
        ).prefetch_related(
            Prefetch(
                "versions",
                queryset=ArticleVersion.objects.select_related("uploaded_by").order_by("-version_number"),
            ),
            Prefetch(
                "review_requests",
                queryset=ReviewRequest.objects.select_related("reviewer", "article_version").order_by("deadline"),
            ),
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

    @staticmethod
    def _compute_transitions(article, is_archived):
        return compute_transitions(_ARTICLE_TRANSITIONS, article, is_archived=is_archived)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        article = self.object
        issue = article.issue
        journal = self.request.journal

        versions = list(article.versions.all())
        review_requests = list(article.review_requests.all())
        reviews_received_count = sum(1 for r in review_requests if r.state == ReviewRequest.State.RECEIVED)
        expected_reviews = [r for r in review_requests if r.state == ReviewRequest.State.EXPECTED]
        received_reviews = sorted(
            [r for r in review_requests if r.state == ReviewRequest.State.RECEIVED],
            key=lambda r: r.received_at or timezone.datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        internal_notes = list(article.internal_notes.all())

        author_options = [
            (c.pk, c.full_name)
            for c in journal.contacts.order_by("last_name", "first_name")
        ]
        if article.author and (article.author_id, article.author.full_name) not in author_options:
            author_options = [(article.author_id, article.author.full_name)] + author_options

        is_archived = issue.state in Issue.ARCHIVED_STATES
        latest_version = versions[0] if versions else None
        next_version_number = (latest_version.version_number + 1) if latest_version else 1
        transition_url = reverse(
            "articles:transition",
            kwargs={
                "slug": journal.slug,
                "issue_id": issue.pk,
                "article_id": article.pk,
            },
        )

        file_upload_url = reverse(
            "articles:file_upload",
            kwargs={"slug": journal.slug, "issue_id": issue.pk, "article_id": article.pk},
        )
        show_file_upload = not is_archived and article.state not in _UPLOAD_BLOCKED_STATES
        file_upload_is_first = article.state == Article.State.PENDING

        ctx.update({
            "issue": issue,
            "journal": journal,
            "internal_notes": internal_notes,
            "author_options": author_options,
            "is_archived": is_archived,
            "versions": versions,
            "version_count": len(versions),
            "latest_version_number": latest_version.version_number if latest_version else None,
            "next_version_number": next_version_number,
            "review_request_count": len(review_requests),
            "reviews_received": reviews_received_count,
            "expected_reviews": expected_reviews,
            "received_reviews": received_reviews,
            "article_count_in_issue": issue.articles.count(),
            "user_journal_count": self.request.user.memberships.count(),
            "reviewer_options": list(
                journal.contacts.filter(
                    usual_roles__overlap=[
                        Contact.Role.INTERNAL_REVIEWER,
                        Contact.Role.EXTERNAL_REVIEWER,
                    ]
                ).order_by("last_name", "first_name")
            ),
            "default_deadline": (
                timezone.now().date() + timezone.timedelta(days=28)
            ).isoformat(),
            "transitions": self._compute_transitions(article, is_archived),
            "transition_url": transition_url,
            "file_upload_url": file_upload_url,
            "show_file_upload": show_file_upload,
            "file_upload_is_first": file_upload_is_first,
        })
        return ctx


class ArticlePatchView(_ArticleJournalMixin, JournalOwnedPatchView):
    ALLOWED_FIELDS = {"title", "author", "author_name_override", "article_type", "abstract"}
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


# ──────────────────────────── Versions ────────────────────────────

_UPLOAD_BLOCKED_STATES = {Article.State.IN_REVIEW, Article.State.VALIDATED}


class ArticleFileUploadView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    # Upload bloqué en in_review pour garantir la cohérence entre fichier en
    # relecture et fichier en base. Pour remplacer un fichier en cours de
    # relecture, faire un rollback in_review → received, déposer, puis
    # renvoyer en relecture.

    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        if article.state in _UPLOAD_BLOCKED_STATES:
            return JsonResponse({"error": "Le dépôt n'est pas autorisé dans cet état."}, status=403)

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "Un fichier est requis."}, status=400)

        is_first = article.state == Article.State.PENDING
        description = request.POST.get("comment", "").strip()

        version = ArticleVersion.objects.create(
            article=article,
            file=file,
            uploaded_by=request.user,
            comment=description,
        )

        actor_name = request.user.get_full_name() or request.user.email
        if is_first:
            article.mark_received()
            article.save()
            msg = f"{actor_name} a déposé le fichier de l'article"
        else:
            msg = f"{actor_name} a déposé la version v{version.version_number}"
        if description:
            msg += f" — {description}"
        log_action(article, request.user, msg)

        return redirect(reverse(
            "articles:detail",
            kwargs={"slug": request.journal.slug, "issue_id": issue_id, "article_id": article_id},
        ))


class ArticleVersionCreateView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        form = ArticleVersionUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": "Fichier requis."}, status=400)

        version = ArticleVersion.objects.create(
            article=article,
            file=form.cleaned_data["file"],
            uploaded_by=request.user,
            comment=form.cleaned_data.get("comment", ""),
        )

        actor_name = request.user.get_full_name() or request.user.email
        comment = form.cleaned_data.get("comment", "").strip()
        msg = f"{actor_name} a déposé la version v{version.version_number}"
        if comment:
            msg += f" — {comment}"
        log_action(article, request.user, msg)

        ctx = {
            "version": version,
            "is_latest": True,
            "article": article,
            "journal": request.journal,
            "issue": article.issue,
            "is_archived": False,
        }
        fragment = render_to_string("articles/_version_item.html", ctx, request=request)
        return HttpResponse(fragment + oob_counters_html(article, request=request))


class ArticleVersionDownloadView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def get(self, request, issue_id, article_id, version_id, **kwargs):
        article = self.get_object_or_404()
        try:
            version = ArticleVersion.objects.get(pk=version_id, article=article)
        except ArticleVersion.DoesNotExist:
            raise Http404

        if not version.file:
            raise Http404

        return file_response(version.file)


# ──────────────────────────── Relectures ────────────────────────────

class ReviewRequestCreateView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        if not article.versions.exists():
            return JsonResponse({"error": "Déposez d'abord une version avant de demander une relecture."}, status=400)

        form = ReviewRequestCreateForm(
            request.POST, journal=request.journal, article=article
        )
        if not form.is_valid():
            errors = {f: [str(e.message) for e in errs] for f, errs in form.errors.as_data().items()}
            return JsonResponse({"errors": errors}, status=400)

        reviewer = form.cleaned_data["reviewer"]
        review = ReviewRequest.objects.create(
            article=article,
            article_version=form.cleaned_data["article_version"],
            reviewer=reviewer,
            reviewer_name_snapshot=reviewer.full_name,
            deadline=form.cleaned_data["deadline"],
            state=ReviewRequest.State.EXPECTED,
        )

        actor_name = request.user.get_full_name() or request.user.email
        deadline_str = review.deadline.strftime("%d/%m/%Y")
        log_action(
            article, request.user,
            f"{actor_name} a demandé une relecture à {reviewer.full_name} pour le {deadline_str}",
        )

        ctx = {
            "review": review,
            "article": article,
            "journal": request.journal,
            "issue": article.issue,
            "is_archived": False,
        }
        fragment = render_to_string("articles/_review_item_expected.html", ctx, request=request)
        return HttpResponse(fragment + oob_counters_html(article, request=request))


class ReviewRequestReceiveView(_ReviewRequestMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, review_id, **kwargs):
        review = self.get_object_or_404()
        article = review.article
        is_archived = article.issue.state in Issue.ARCHIVED_STATES

        if is_archived:
            return JsonResponse({"error": "Cet article ne peut plus être modifié."}, status=403)
        if review.state == ReviewRequest.State.RECEIVED:
            return JsonResponse({"error": "Cette relecture a déjà été enregistrée."}, status=400)

        form = ReviewRequestReceiveForm(request.POST, request.FILES, instance=review)
        if not form.is_valid():
            errors = {f: [str(e.message) for e in errs] for f, errs in form.errors.as_data().items()}
            return JsonResponse({"errors": errors}, status=400)

        review = form.save(commit=False)
        review.state = ReviewRequest.State.RECEIVED
        review.received_at = timezone.now()
        review.save()

        verdict_label = review.get_verdict_display()
        log_action(
            article, request.user,
            f"Relecture de {review.reviewer_name_snapshot} reçue — verdict : {verdict_label}",
        )

        ctx = {
            "review": review,
            "article": article,
            "journal": request.journal,
            "issue": article.issue,
            "is_archived": is_archived,
        }
        received_html = render_to_string("articles/_review_item_received.html", ctx, request=request)
        oob_received = (
            f'<div hx-swap-oob="afterbegin:#reviews-received-list">{received_html}</div>'
        )
        return HttpResponse(oob_received + oob_counters_html(article, request=request))


class ReviewRequestDeleteView(_ReviewRequestMixin, JournalMemberRequiredMixin, View):
    def post(self, request, issue_id, article_id, review_id, **kwargs):
        review = self.get_object_or_404()
        article = review.article

        guard = self._check_archived(article)
        if guard:
            return guard
        if review.state == ReviewRequest.State.RECEIVED:
            return JsonResponse({"error": "Une relecture reçue ne peut pas être supprimée."}, status=400)

        name = review.reviewer_name_snapshot
        review.delete()
        log_action(article, request.user, f"Demande de relecture à {name} annulée")

        return HttpResponse(oob_counters_html(article, request=request))


class ReviewRequestFileDownloadView(_ReviewRequestMixin, JournalMemberRequiredMixin, View):
    def get(self, request, issue_id, article_id, review_id, **kwargs):
        review = self.get_object_or_404()

        if not review.received_file:
            raise Http404

        return file_response(review.received_file)


class ReviewRequestPatchView(_ReviewRequestMixin, JournalOwnedPatchView):
    ALLOWED_FIELDS = {"deadline", "internal_notes", "verdict"}
    FULL_CLEAN_EXCLUDE = []

    def check_editable(self, obj):
        return self._check_archived(obj.article)

    def get_allowed_fields(self, obj):
        if obj.state == ReviewRequest.State.EXPECTED:
            return {"deadline", "internal_notes"}
        if obj.state == ReviewRequest.State.RECEIVED:
            return {"internal_notes", "verdict"}
        return set()


class ArticleTransitionView(_ArticleJournalMixin, JournalOwnedTransitionView):
    TRANSITION_SPECS = _ARTICLE_TRANSITIONS

    def check_transition_allowed(self, article):
        return self._check_archived(article)

    def create_audit_note(self, obj, user, message):
        InternalNote.objects.create(article=obj, author=user, content=message, is_automatic=True)

    def get_success_url(self, obj):
        return reverse(
            "articles:detail",
            kwargs={
                "slug": self.request.journal.slug,
                "issue_id": self.kwargs["issue_id"],
                "article_id": obj.pk,
            },
        )


class ArticleMarkReceivedView(_ArticleJournalMixin, JournalMemberRequiredMixin, View):
    """Transition pending → received + création de la version v1."""

    def post(self, request, issue_id, article_id, **kwargs):
        article = self.get_object_or_404()

        guard = self._check_archived(article)
        if guard:
            return guard

        if article.state != Article.State.PENDING:
            return JsonResponse({"error": "L'article n'est pas en attente de réception."}, status=400)

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "Un fichier est requis pour marquer l'article comme reçu."}, status=400)

        article.mark_received()
        article.save()

        version = ArticleVersion.objects.create(
            article=article,
            file=file,
            uploaded_by=request.user,
        )

        actor_name = request.user.get_full_name() or request.user.email
        log_action(
            article, request.user,
            f"{actor_name} a marqué l'article comme reçu et déposé la version v{version.version_number}",
        )

        return JsonResponse({
            "redirect_url": reverse(
                "articles:detail",
                kwargs={"slug": request.journal.slug, "issue_id": issue_id, "article_id": article_id},
            )
        })
