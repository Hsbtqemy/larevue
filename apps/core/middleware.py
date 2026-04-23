import re

from django.utils.functional import SimpleLazyObject

# Correspond à /revues/<slug>/ et à tous les sous-chemins de la revue.
_JOURNAL_URL_RE = re.compile(r"^/revues/(?P<slug>[a-zA-Z0-9_-]+)/")


def _get_journal_by_slug(slug):
    from apps.journals.models import Journal

    try:
        return Journal.objects.get(slug=slug)
    except Journal.DoesNotExist:
        return None


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
