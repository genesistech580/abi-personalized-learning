"""Alwaysdata entry point for the /abitech deployment."""
import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

root = Path(__file__).resolve().parent.parent
environment_file = root / ".hosting-env"
if environment_file.exists():
    for line in environment_file.read_text().splitlines():
        if line.startswith("export "):
            name, value = line[7:].split("=", 1)
            os.environ.setdefault(name, value)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.hosting"
django_application = get_wsgi_application()

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.handlers.wsgi import WSGIRequest
from django.http import Http404, HttpResponseNotFound
from django.views.static import serve


def application(environ, start_response):
    prefix = "/abitech"
    path = environ.get("PATH_INFO", "/")
    if path == prefix or path.startswith(prefix + "/"):
        path = path[len(prefix):] or "/"
    environ["PATH_INFO"] = path
    environ["SCRIPT_NAME"] = prefix

    if path.startswith("/static/"):
        request = WSGIRequest(environ)
        try:
            response = serve(request, path[len("/static/"):], document_root=settings.STATIC_ROOT)
        except (Http404, SuspiciousFileOperation):
            response = HttpResponseNotFound()
        response["X-Content-Type-Options"] = "nosniff"
        if response.status_code == 200:
            response["Cache-Control"] = "public, max-age=300"
        start_response(
            f"{response.status_code} {response.reason_phrase}", list(response.items())
        )
        return response

    return django_application(environ, start_response)

