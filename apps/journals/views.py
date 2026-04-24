from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.articles.models import Article
from apps.core.display import MONTH_ABBR
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

        late_reviews = [
            {
                "review": rr,
                "article": rr.article,
                "issue": rr.article.issue,
                "days_overdue": (today - rr.deadline).days,
            }
            for rr in all_expected if rr.deadline < today
        ]

        # Map current issue state → the deadline field that is "currently due"
        _state_deadline = {
            Issue.State.ACCEPTED: "deadline_articles",
            Issue.State.IN_REVIEW: "deadline_reviews",
            Issue.State.IN_REVISION: "deadline_v2",
            Issue.State.FINAL_CHECK: "deadline_final_check",
            Issue.State.SENT_TO_PUBLISHER: "deadline_sent_to_publisher",
        }
        _deadline_labels = {
            "deadline_articles": "Limite articles",
            "deadline_reviews": "Limite relectures",
            "deadline_v2": "Limite V2",
            "deadline_final_check": "Limite vérif. finale",
            "deadline_sent_to_publisher": "Limite envoi éditeur",
            "planned_publication_date": "Parution prévue",
        }

        late_issues = []
        for issue in active_issues:
            issue.is_late = False
            field = _state_deadline.get(issue.state)
            if field:
                d = getattr(issue, field)
                if d and d < today:
                    issue.is_late = True
                    issue.late_label = _deadline_labels[field]
                    issue.days_overdue = (today - d).days
                    late_issues.append({
                        "issue": issue,
                        "deadline": d,
                        "label": _deadline_labels[field],
                        "days_overdue": issue.days_overdue,
                    })

        # Upcoming deadlines: review deadlines + all 5 issue deadline fields + planned publication
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
            for field, label in _deadline_labels.items():
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
            "late_reviews": late_reviews,
            "late_issues": late_issues,
            "late_count": len(late_reviews) + len(late_issues),
            "upcoming_deadlines": upcoming[:10],
            "user_journal_count": self.request.user.memberships.count(),
        })
        return ctx
