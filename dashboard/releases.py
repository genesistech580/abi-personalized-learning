from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def release_version():
    try:
        return (settings.BASE_DIR / "deployment" / "release.txt").read_text().strip()
    except OSError:
        return "local"


def activity_version():
    try:
        return str((settings.BASE_DIR / ".activity-version").stat().st_mtime_ns)
    except OSError:
        return "0"


def release_context(request):
    return {
        "release_version": release_version(),
        "activity_version": activity_version() if request.user.is_authenticated else "",
    }


@never_cache
@require_GET
def system_version(request):
    data = {"version": release_version()}
    if request.user.is_authenticated:
        data["activity"] = activity_version()
    return JsonResponse(data)
