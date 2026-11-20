from .models import ServiceStatus


def record_service(service, successful, summary):
    # Callers supply fixed messages, never provider response bodies or credentials.
    ServiceStatus.objects.update_or_create(service=service, defaults={"successful": successful, "summary": summary})
