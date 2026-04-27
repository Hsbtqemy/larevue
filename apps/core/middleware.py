import re

from django.urls import reverse
from django.utils.functional import SimpleLazyObject

# Correspond à /revues/<slug>/ et à tous les sous-chemins de la revue.
_JOURNAL_URL_RE = re.compile(r"^/revues/(?P<slug>[a-zA-Z0-9_-]+)/")


def _get_journal_by_slug(slug):
    from apps.journals.models import Journal

    try:
        return Journal.objects.get(slug=slug)
    except Journal.DoesNotExist:
        return None


_MUST_CHANGE_EXEMPT_PREFIXES = ("/accounts/", "/admin/", "/static/", "/media/")


class MustChangePasswordMiddleware:
    """Redirect authenticated users with must_change_password=True to the password change page.

    Exemptions: the password-change URL itself, allauth/admin/static/media paths,
    and unauthenticated requests (handled by LoginRequired elsewhere).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._redirect_url = None

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, "must_change_password", False)
            and not self._is_exempt(request.path)
        ):
            redirect_url = self._get_redirect_url()
            if request.path != redirect_url:
                from django.shortcuts import redirect
                return redirect(redirect_url)
        return self.get_response(request)

    def _get_redirect_url(self):
        if self._redirect_url is None:
            self._redirect_url = reverse("accounts:profile_password")
        return self._redirect_url

    def _is_exempt(self, path):
        return any(path.startswith(prefix) for prefix in _MUST_CHANGE_EXEMPT_PREFIXES)


class CurrentJournalMiddleware:
    """
    Injecte `request.journal` à partir du slug présent dans l'URL.
    - URLs hors revue (/admin/, /accounts/, /) → request.journal = None directement.
    - URLs /revues/<slug>/... → request.journal = SimpleLazyObject (évalué à la demande).
    Retourne None sans lever d'exception si le slug ne correspond à aucune revue.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        match = _JOURNAL_URL_RE.match(request.path)
        if match:
            slug = match.group("slug")
            request.journal = SimpleLazyObject(lambda: _get_journal_by_slug(slug))
        else:
            # Pas de slug dans l'URL : on sait immédiatement qu'il n'y a pas de revue active.
            request.journal = None
        return self.get_response(request)
