from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.core.mixins import JournalMemberRequiredMixin
from apps.issues.models import Issue


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get(self, request, *args, **kwargs):
        journals = [m.journal for m in request.user.memberships.select_related("journal").all()]
        if len(journals) == 1:
            return redirect("journal_dashboard", slug=journals[0].slug)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["journals"] = [
            m.journal for m in self.request.user.memberships.select_related("journal").all()
        ]
        return ctx


class JournalDashboardView(JournalMemberRequiredMixin, TemplateView):
    template_name = "journals/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        # Lever Http404 avant le contrôle de membership pour ne pas exposer
        # un 403 sur une revue qui n'existe pas.
        # `not request.journal` évalue le SimpleLazyObject si nécessaire.
        if not request.journal:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        journal = self.request.journal
        active_issues = journal.issues.filter(
            state__in=[
                Issue.State.UNDER_REVIEW,
                Issue.State.ACCEPTED,
                Issue.State.IN_PRODUCTION,
                Issue.State.SENT_TO_PUBLISHER,
            ]
        ).order_by("-number")
        ctx["journal"] = journal
        ctx["active_issues"] = active_issues
        ctx["user_journal_count"] = self.request.user.memberships.count()
        return ctx
