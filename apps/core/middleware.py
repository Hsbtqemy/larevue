from django.utils.functional import SimpleLazyObject


def _get_current_journal(request):
    """
    Résout la revue active à partir du slug injecté par le routeur d'URL.
    Retourne None sur les pages sans contexte de revue (admin, auth).
    """
    from apps.journals.models import Journal

    slug = getattr(request, "_journal_slug", None)
    if not slug:
        return None
    try:
        return Journal.objects.get(slug=slug)
    except Journal.DoesNotExist:
        return None


class CurrentJournalMiddleware:
    """
    Injecte `request.journal` (évalué paresseusement) depuis le slug d'URL.
    Les vues URL doivent peupler `request._journal_slug` via un convertisseur
    de chemin ou un middleware de routage avant que ce middleware ne s'exécute.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.journal = SimpleLazyObject(lambda: _get_current_journal(request))
        return self.get_response(request)
