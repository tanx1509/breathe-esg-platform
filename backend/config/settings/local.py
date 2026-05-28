"""
Local development settings — SQLite, DEBUG=True, relaxed CORS.
"""
from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# SQLite for local development
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# CORS — allow React dev server
CORS_ALLOW_ALL_ORIGINS = True
