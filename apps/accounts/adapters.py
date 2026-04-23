from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """
    Désactive l'inscription publique : les comptes sont créés exclusivement
    via l'admin Django par l'administrateur technique.
    """

    def is_open_for_signup(self, request):
        return False
