# AI Sharc — mailer adapter. Console backend logs the magic link (dev/tests);
# SMTP and SendGrid backends are configured via environment variables.
# SPF, DKIM and DMARC are DNS records Tim adds at the registrar — see SETUP.md.
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("aisharc.mailer")


class Mailer:
    """Interface: send(to, subject, text)."""

    def send(self, to, subject, text):
        raise NotImplementedError


class ConsoleMailer(Mailer):
    """Dev/test backend — writes the message to the log, never sends."""

    def send(self, to, subject, text):
        log.info("MAIL to=%s subject=%s\n%s", to, subject, text)


class SmtpMailer(Mailer):
    def send(self, to, subject, text):
        msg = EmailMessage()
        msg["From"] = settings.mail_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)


class SendGridMailer(Mailer):
    """SMTP relay via SendGrid — set SENDGRID_API_KEY and use the smtp backend,
    or this direct HTTP backend. HTTP API used so no SMTP credentials are stored."""

    def send(self, to, subject, text):
        import json as _json
        import urllib.request

        payload = _json.dumps({
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": settings.mail_from, "name": "AI Sharc"},
            "subject": subject,
            "content": [{"type": "text/plain", "value": text}],
        }).encode()
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send", data=payload,
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            }, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"sendgrid status {resp.status}")


def get_mailer():
    name = settings.mailer.lower()
    if name == "smtp":
        return SmtpMailer()
    if name == "sendgrid":
        return SendGridMailer()
    return ConsoleMailer()


def send_verification_email(to, verify_url):
    subject = "Your AI Sharc verification link (one click)"
    text = (
        "Thanks for requesting your free AI Sharc Preliminary Report Card.\n\n"
        "Confirm it's you — one click:\n"
        f"{verify_url}\n\n"
        "This link works once and expires in "
        f"{settings.verify_token_ttl_minutes} minutes. We'll scan your site and\n"
        "your card will be ready to view — free, always.\n\n"
        "Didn't request this? Ignore this email.\n\n"
        "AI Sharc · PO Box 1622, Coppell, TX 75019\n"
    )
    get_mailer().send(to, subject, text)
