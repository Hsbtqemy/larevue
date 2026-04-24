from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.articles.models import Article
from apps.core.display import DEADLINE_LABELS, MONTH_ABBR
from apps.core.mixins import JournalMemberRequiredMixin
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest


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
            .order_by("-number")
        )
        for issue in active_issues:
            issue.pct = (
                int(issue.validated_count / issue.article_count * 100)
                if issue.article_count > 0
                else 0
            )

        # Fetch all expected reviews for active issues in one query, then split by date.
        all_expected = list(
            ReviewRequest.objects
            .filter(
                state=ReviewRequest.State.EXPECTED,
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
        for rr in all_expected:
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
        for rr in all_expected:
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
        })
        return ctx
