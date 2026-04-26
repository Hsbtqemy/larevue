import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string

try:
    import weasyprint
except OSError:
    weasyprint = None
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.articles.models import Article
from apps.core.display import DEADLINE_LABELS, DEADLINE_TYPES, MONTH_ABBR
from apps.core.mixins import JournalMemberRequiredMixin
from apps.core.utils import file_response
from apps.issues.models import Issue
from apps.journals.forms import JournalDocumentForm, JournalEditForm
from apps.journals.models import JournalDocument
from apps.reviews.models import ReviewRequest


def _build_calendar_events(journal, active_issues=None):
    if active_issues is None:
        active_issues = list(journal.issues.filter(state__in=Issue.ACTIVE_STATES))

    events = []
    for issue in active_issues:
        url = reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": issue.pk})
        for field, evt_type in DEADLINE_TYPES.items():
            d = getattr(issue, field)
            if d:
                events.append({
                    "date": d.isoformat(),
                    "type": evt_type,
                    "label": f"{DEADLINE_LABELS[field]} · N°{issue.number}",
                    "url": url,
                })

    for rr in (
        ReviewRequest.objects
        .filter(state=ReviewRequest.State.SENT, article__issue__in=active_issues)
        .select_related("article__issue")
    ):
        url = reverse("issues:detail", kwargs={"slug": journal.slug, "issue_id": rr.article.issue_id})
        events.append({
            "date": rr.deadline.isoformat(),
            "type": "review_request",
            "label": f"Relecture · {rr.reviewer_name_snapshot}",
            "url": url,
        })

    return events


def _get_journal_document_or_404(request, doc_id):
    try:
        return JournalDocument.objects.get(pk=doc_id, journal=request.journal)
    except JournalDocument.DoesNotExist:
        raise Http404


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def _get_journals(self):
        if not hasattr(self, "_journals"):
            self._journals = [
                m.journal
                for m in self.request.user.memberships.select_related("journal").all()
            ]
        return self._journals

    def get(self, request, *args, **kwargs):
        journals = self._get_journals()
        if len(journals) == 1:
            return redirect("journal_dashboard", slug=journals[0].slug)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["journals"] = self._get_journals()
        return ctx


class JournalDashboardView(JournalMemberRequiredMixin, TemplateView):
    template_name = "journals/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        journal = self.request.journal
        today = timezone.now().date()

        active_issues = list(
            journal.issues
            .filter(state__in=Issue.ACTIVE_STATES)
            .annotate(
                article_count=Count("articles"),
                validated_count=Count(
                    "articles", filter=Q(articles__state=Article.State.VALIDATED)
                ),
            )
            .order_by(F("planned_publication_date").asc(nulls_last=True))
        )
        for issue in active_issues:
            issue.pct = (
                int(issue.validated_count / issue.article_count * 100)
                if issue.article_count > 0
                else 0
            )

        all_sent = list(
            ReviewRequest.objects
            .filter(
                state=ReviewRequest.State.SENT,
                article__issue__in=active_issues,
            )
            .select_related("article", "article__issue")
            .order_by("deadline")
        )

        # Maps current state → deadline field that is "currently due" for lateness detection.
        # Offset by one from the timeline's _STATE_DEADLINE_FIELD: when ACCEPTED, you're
        # working toward articles (so deadline_articles is what you track for lateness).
        _state_deadline = {
            Issue.State.ACCEPTED: "deadline_articles",
            Issue.State.IN_REVIEW: "deadline_reviews",
            Issue.State.IN_REVISION: "deadline_v2",
            Issue.State.FINAL_CHECK: "deadline_final_check",
            Issue.State.SENT_TO_PUBLISHER: "deadline_sent_to_publisher",
        }

        watch_items = []
        for rr in all_sent:
            if rr.deadline < today:
                watch_items.append({
                    "type": "review",
                    "review": rr,
                    "article": rr.article,
                    "issue": rr.article.issue,
                    "days_overdue": (today - rr.deadline).days,
                })
        for issue in active_issues:
            issue.is_late = False
            field = _state_deadline.get(issue.state)
            if field:
                d = getattr(issue, field)
                if d and d < today:
                    days_overdue = (today - d).days
                    issue.is_late = True
                    issue.days_overdue = days_overdue
                    watch_items.append({
                        "type": "issue",
                        "issue": issue,
                        "deadline": d,
                        "label": DEADLINE_LABELS[field],
                        "days_overdue": days_overdue,
                    })
        watch_items.sort(key=lambda x: x["days_overdue"], reverse=True)

        upcoming = []
        for rr in all_sent:
            if rr.deadline >= today:
                upcoming.append({
                    "type": "review",
                    "date": rr.deadline,
                    "day": rr.deadline.day,
                    "month": MONTH_ABBR[rr.deadline.month - 1],
                    "review": rr,
                    "article": rr.article,
                    "issue": rr.article.issue,
                })
        for issue in active_issues:
            for field, label in DEADLINE_LABELS.items():
                d = getattr(issue, field, None)
                if d and d >= today:
                    upcoming.append({
                        "type": "issue_deadline",
                        "date": d,
                        "day": d.day,
                        "month": MONTH_ABBR[d.month - 1],
                        "label": label,
                        "issue": issue,
                    })
        upcoming.sort(key=lambda x: x["date"])

        ctx.update({
            "journal": journal,
            "active_issues": active_issues,
            "watch_items": watch_items,
            "late_count": len(watch_items),
            "upcoming_deadlines": upcoming[:10],
            "user_journal_count": self.request.user.memberships.count(),
            "calendar_events": _build_calendar_events(journal, active_issues),
            "today_iso": today.isoformat(),
        })
        return ctx


def _archived_issues_qs(journal, state_filter=None):
    qs = (
        journal.issues
        .filter(state__in=Issue.ARCHIVED_STATES)
        .annotate(
            article_count=Count("articles", distinct=True),
            reviews_received_count=Count(
                "articles__review_requests",
                filter=Q(articles__review_requests__state="received"),
                distinct=True,
            ),
        )
        .order_by(F("published_at").desc(nulls_last=True), F("refused_at").desc(nulls_last=True))
    )
    if state_filter in (Issue.State.PUBLISHED, Issue.State.REFUSED):
        qs = qs.filter(state=state_filter)
    return qs


class JournalArchivesView(JournalMemberRequiredMixin, TemplateView):
    template_name = "journals/archives.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        journal = self.request.journal

        archived_issues = list(_archived_issues_qs(journal))

        years_data: dict[int, list] = {}
        for issue in archived_issues:
            year = issue.archive_date.year if issue.archive_date else 0
            years_data.setdefault(year, []).append(issue)

        ctx.update({
            "journal": journal,
            "years_groups": [
                (year, years_data[year])
                for year in sorted(years_data.keys(), reverse=True)
            ],
            "total_count": len(archived_issues),
            "export_url": reverse("journal_archives_export", kwargs={"slug": journal.slug}),
        })
        return ctx


class JournalArchivesExportView(JournalMemberRequiredMixin, View):
    def get(self, request, **kwargs):
        journal = request.journal
        state_filter = request.GET.get("state", "")
        issues = list(_archived_issues_qs(journal, state_filter=state_filter))

        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        slug = journal.slug
        state_suffix = f"_{state_filter}" if state_filter else ""
        response["Content-Disposition"] = f'attachment; filename="archives_{slug}{state_suffix}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Numéro", "Titre thématique", "Responsable éditorial·e",
            "État", "Articles", "Relectures reçues", "Date archivage",
        ])
        state_labels = dict(Issue.State.choices)
        for issue in issues:
            writer.writerow([
                issue.number,
                issue.thematic_title,
                issue.editor_name,
                state_labels.get(issue.state, issue.state),
                issue.article_count,
                issue.reviews_received_count,
                issue.archive_date.strftime("%d/%m/%Y") if issue.archive_date else "",
            ])
        return response


class JournalBilanReportView(JournalMemberRequiredMixin, View):
    def get(self, request, **kwargs):
        journal = request.journal
        try:
            year = int(request.GET.get("year", 0))
        except (ValueError, TypeError):
            year = 0
        if not year:
            raise Http404

        issues = list(
            _archived_issues_qs(journal).filter(
                Q(published_at__year=year) | Q(refused_at__year=year)
            )
        )

        ctx = {
            "journal": journal,
            "year": year,
            "issues": issues,
            "total_issues": len(issues),
            "published_count": sum(1 for i in issues if i.state == Issue.State.PUBLISHED),
            "refused_count": sum(1 for i in issues if i.state == Issue.State.REFUSED),
            "total_articles": sum(i.article_count for i in issues),
            "total_reviews_received": sum(i.reviews_received_count for i in issues),
            "generated_at": timezone.now(),
        }
        html = render_to_string("journals/bilan.html", ctx, request=request)

        if weasyprint is not None:
            pdf = weasyprint.HTML(string=html).write_pdf()
            filename = f"bilan_{journal.slug}_{year}.pdf"
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return HttpResponse(html, content_type="text/html")


class JournalDocumentCreateView(JournalMemberRequiredMixin, View):
    def post(self, request, **kwargs):
        form = JournalDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.journal = request.journal
            doc.uploaded_by = request.user
            doc.save()
        return redirect(reverse("journal_edit", kwargs={"slug": request.journal.slug}))


class JournalDocumentDeleteView(JournalMemberRequiredMixin, View):
    def post(self, request, doc_id, **kwargs):
        doc = _get_journal_document_or_404(request, doc_id)
        doc.delete()
        return redirect(reverse("journal_edit", kwargs={"slug": request.journal.slug}))


class JournalDocumentDownloadView(JournalMemberRequiredMixin, View):
    def get(self, request, doc_id, **kwargs):
        doc = _get_journal_document_or_404(request, doc_id)
        if not doc.file:
            raise Http404
        return file_response(doc.file)


class JournalEditView(JournalMemberRequiredMixin, View):
    template_name = "journals/edit.html"

    def _context(self, form):
        journal = self.request.journal
        _kw = {"slug": journal.slug}
        documents = list(journal.documents.select_related("uploaded_by"))
        for doc in documents:
            doc.download_url = reverse("journal_document_download", kwargs={**_kw, "doc_id": doc.pk})
            doc.delete_url = reverse("journal_document_delete", kwargs={**_kw, "doc_id": doc.pk})
        return {
            "journal": journal,
            "form": form,
            "documents": documents,
            "doc_create_url": reverse("journal_document_create", kwargs=_kw),
            "doc_section_title": "Documents de la revue",
            "doc_add_modal_title": "Ajouter un document à la revue",
            "is_editable": True,
            "user_journal_count": self.request.user.memberships.count(),
        }

    def get(self, request, **kwargs):
        form = JournalEditForm(instance=request.journal)
        return render(request, self.template_name, self._context(form))

    def post(self, request, **kwargs):
        form = JournalEditForm(request.POST, request.FILES, instance=request.journal)
        if form.is_valid():
            form.save()
            return redirect(reverse("journal_edit", kwargs={"slug": request.journal.slug}))
        return render(request, self.template_name, self._context(form))
