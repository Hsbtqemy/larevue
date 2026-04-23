from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class JournalMemberRequiredMixin(LoginRequiredMixin):
    """
    Vérifie, avant d'exécuter la vue, que l'utilisateur·ice est membre de la
    revue active. Nécessite CurrentJournalMiddleware sur les URLs /revues/<slug>/.

    Ordre des contrôles :
    1. Non connecté·e → redirect login (via handle_no_permission)
    2. Revue active mais non membre → 403
    3. Sinon → vue exécutée normalement

    Note : `if journal` (et non `is not None`) pour évaluer correctement un
    SimpleLazyObject wrappant None — le ORM n'accepte pas ce type brut.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        journal = getattr(request, "journal", None)
        if journal and not request.user.memberships.filter(journal=journal).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
