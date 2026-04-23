from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def journal_member_required(view_func):
    """Équivalent fonctionnel de JournalMemberRequiredMixin."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        journal = getattr(request, "journal", None)
        if journal and not request.user.memberships.filter(journal=journal).exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
