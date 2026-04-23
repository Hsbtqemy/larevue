from .base import *  # noqa: F401, F403

DEBUG = True

# Pas de vérification e-mail en local
ACCOUNT_EMAIL_VERIFICATION = "none"

# Console backend pour voir les e-mails dans le terminal
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# django-extensions pour shell_plus
INSTALLED_APPS += ["django_extensions"]  # noqa: F405
