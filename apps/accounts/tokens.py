from django.core import signing

_SALT = "reviewer-invitation-v1"
_MAX_AGE = 7 * 24 * 3600  # 7 jours


def make_invitation_token(user_pk: int) -> str:
    return signing.dumps(user_pk, salt=_SALT)


def load_invitation_token(token: str) -> int:
    """Retourne le user_pk. Lève SignatureExpired ou BadSignature si invalide."""
    return signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
