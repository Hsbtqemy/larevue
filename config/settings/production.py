from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")

# WhiteNoise doit être inséré juste après SecurityMiddleware
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# HTTPS — mettre HTTPS_ENABLED=False lors du déploiement initial sans TLS,
# puis repasser à True une fois certbot configuré.
HTTPS_ENABLED = config("HTTPS_ENABLED", default=True, cast=bool)

SECURE_SSL_REDIRECT = HTTPS_ENABLED
SESSION_COOKIE_SECURE = HTTPS_ENABLED
CSRF_COOKIE_SECURE = HTTPS_ENABLED

if HTTPS_ENABLED:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# E-mail SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@example.com")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": config("LOG_FILE", default="/var/log/edito/edito.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "delay": True,
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Sentry — décommenter et installer sentry-sdk si besoin
# import sentry_sdk
# SENTRY_DSN = config("SENTRY_DSN", default="")
# if SENTRY_DSN:
#     sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)
