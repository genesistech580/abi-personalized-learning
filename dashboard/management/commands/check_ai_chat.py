"""Safe AI diagnostics: report configuration and make an optional tiny test request."""
import json
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from django.conf import settings
from django.core.management.base import BaseCommand
from dashboard.models import ServiceStatus
from dashboard.services import record_service


class Command(BaseCommand):
    help = "Report AI status without exposing keys. --probe sends one short test request."

    def add_arguments(self, parser):
        parser.add_argument("--probe", action="store_true")

    def handle(self, *args, **options):
        configured = bool(settings.OPENAI_API_KEY.strip())
        self.stdout.write("AI key configured: " + str(configured))
        self.stdout.write("AI model: " + repr(settings.OPENAI_CHAT_MODEL[:100]))
        last = ServiceStatus.objects.filter(service="ai").first()
        if last:
            self.stdout.write("Last request successful: " + str(last.successful))
            self.stdout.write("Last status: " + last.summary)
        if not configured or not options["probe"]:
            return
        request = Request("https://api.openai.com/v1/responses", method="POST",
            data=json.dumps({"model": settings.OPENAI_CHAT_MODEL, "input": "Reply with OK.", "store": False, "max_output_tokens": 64}).encode(),
            headers={"Authorization": "Bearer " + settings.OPENAI_API_KEY.strip(), "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            text = " ".join(part.get("text", "") for item in data.get("output", []) if item.get("type") == "message" for part in item.get("content", []) if part.get("type") == "output_text")
            success = bool(text.strip())
            summary = "AI diagnostic request succeeded." if success else "AI diagnostic returned no text."
            self.stdout.write("Probe successful: " + str(success))
            self.stdout.write("Response status: " + str(data.get("status", "unknown")))
        except HTTPError as error:
            try:
                code = json.load(error).get("error", {}).get("code")
            except (OSError, ValueError, AttributeError):
                code = None
            safe_code = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,80}", code) else "unknown_error"
            success = False
            summary = f"AI request failed: HTTP {error.code}, {safe_code}."
            self.stdout.write(summary)
        except (OSError, ValueError, TypeError):
            success = False
            summary = "AI diagnostic connection or response failed."
            self.stdout.write(summary)
        record_service("ai", success, summary)
