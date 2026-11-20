import logging
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from dashboard.services import record_service

logger = logging.getLogger(__name__)


class MonitoredPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        body = loader.render_to_string(email_template_name, context)
        message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name:
            message.attach_alternative(loader.render_to_string(html_email_template_name, context), "text/html")
        try:
            accepted = bool(message.send())
        except Exception:
            record_service("email", False, "Password-reset mail could not be sent.")
            logger.warning("Password-reset email delivery failed; check private SMTP configuration.")
        else:
            record_service("email", accepted, "Mail backend accepted the message." if accepted else "Mail backend did not accept the message.")
