from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def release_version():
    try:
        return (settings.BASE_DIR / "deployment" / "release.txt").read_text().strip()
    except OSError:
        return "local"


def release_context(request):
    return {"release_version": release_version()}


@never_cache
@require_GET
def system_version(request):
    return JsonResponse({"version": release_version()})
