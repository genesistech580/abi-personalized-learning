"""HTTPS deployment settings for Alwaysdata."""
from .settings import *

from django.core.exceptions import ImproperlyConfigured

DEBUG = False
SECRET_KEY = environ.get("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = environ.get("DJANGO_ALLOWED_HOSTS", "").split()
if len(SECRET_KEY) < 50 or not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY (50+ characters) and DJANGO_ALLOWED_HOSTS.")

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]
FORCE_SCRIPT_NAME = "/abitech"
STATIC_URL = "/abitech/static/"
SESSION_COOKIE_PATH = "/abitech/"
CSRF_COOKIE_PATH = "/abitech/"
STATIC_ROOT = BASE_DIR / "staticfiles"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_CONTENT_TYPE_NOSNIFF = True

# Isolate this application from the other site on the same hostname.
SESSION_COOKIE_NAME = "abitech_session"
CSRF_COOKIE_NAME = "abitech_csrf"
SECURE_REFERRER_POLICY = "same-origin"
DATABASES["default"]["OPTIONS"] = {"timeout": 20}
