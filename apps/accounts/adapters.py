from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """
    Désactive l'inscription publique : les comptes sont créés exclusivement
    via l'admin Django par l'administrateur technique.
    """

    def is_open_for_signup(self, request):
        return False

    def get_client_ip(self, request):
        # Behind nginx proxy: REMOTE_ADDR is empty (unix socket).
        # Use X-Real-IP (set by nginx) or fall back to X-Forwarded-For.
        ip = request.META.get("HTTP_X_REAL_IP")
        if not ip:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = forwarded.split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "")
        if not ip:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Unable to determine client IP address")
        return ip
