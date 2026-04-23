from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class JournalMemberRequiredMixin(LoginRequiredMixin):
    """
    Vérifie que l'utilisateur·ice connecté·e est membre de la revue active.
    Nécessite CurrentJournalMiddleware et une URL avec slug de revue.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated:
            journal = getattr(request, "journal", None)
            if journal and not request.user.memberships.filter(journal=journal).exists():
                raise PermissionDenied
        return response
