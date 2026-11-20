"""AI diagnostics without printing keys, prompts or provider response bodies."""
from django.core.management.base import BaseCommand
from dashboard.chat import chat_configuration, request_reply, ChatError
from dashboard.models import ServiceStatus
from dashboard.services import record_service


class Command(BaseCommand):
    help = "Report AI status without exposing keys. --probe sends one short test request."

    def add_arguments(self, parser):
        parser.add_argument("--probe", action="store_true")

    def handle(self, *args, **options):
        key, model = chat_configuration()
        self.stdout.write("AI key configured: " + str(bool(key)))
        self.stdout.write("AI model: " + repr(model[:100]))
        last = ServiceStatus.objects.filter(service="ai").first()
        if last:
            self.stdout.write("Last request successful: " + str(last.successful))
            self.stdout.write("Last status: " + last.summary)
        if not key or not options["probe"]:
            return
        try:
            request_reply([{"role": "user", "content": "Reply with OK."}], "Connection check.", max_tokens=64)
        except ChatError as error:
            success = False
            summary = "AI diagnostic failed: " + error.code + "."
        else:
            success = True
            summary = "AI diagnostic request succeeded."
        self.stdout.write("Probe successful: " + str(success))
        self.stdout.write(summary)
        record_service("ai", success, summary)
