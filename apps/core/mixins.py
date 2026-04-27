from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404


class SuperuserRequiredMixin(LoginRequiredMixin):
    """Allow access only to authenticated superusers; others get 403."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class JournalOwnedObjectMixin:
    """Mixin for views that operate on a single object belonging to the current journal.

    Subclasses set:
    - model: the Django model class
    - pk_url_kwarg: URL kwarg name for the object PK
    - journal_field_path: ORM lookup path to the journal (e.g. "journal" for Issue,
      "issue__journal" for Article)
    """

    model = None
    pk_url_kwarg = "pk"
    journal_field_path = "journal"

    def get_object_or_404(self):
        try:
            return self.model.objects.get(
                pk=self.kwargs[self.pk_url_kwarg],
                **{self.journal_field_path: self.request.journal},
            )
        except self.model.DoesNotExist:
            raise Http404


class JournalMemberRequiredMixin(LoginRequiredMixin):
    """
    Vérifie, avant d'exécuter la vue, que l'utilisateur·ice est membre de la
    revue active. Nécessite CurrentJournalMiddleware sur les URLs /revues/<slug>/.

    Ordre des contrôles :
    1. Revue inexistante → 404 (évite de divulguer une 403 sur un slug inconnu)
    2. Non connecté·e → redirect login (via handle_no_permission)
    3. Revue active mais non membre → 403
    4. Sinon → vue exécutée normalement

    Note : `if not request.journal` évalue correctement un SimpleLazyObject
    wrappant None — le ORM n'accepte pas ce type brut.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.journal:
            raise Http404
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.memberships.filter(journal=request.journal).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
