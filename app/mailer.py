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


def send_dashboard_login_email(to, login_url):
    subject = "Your AI Sharc dashboard link (one click)"
    text = (
        "Your AI Sharc dashboard is one click away:\n\n"
        f"{login_url}\n\n"
        "This link works once and expires in 30 minutes. From the dashboard you can\n"
        "view your Report Cards, download PDFs and manage your monitoring "
        "subscription.\n\n"
        "Didn't request this? Ignore this email.\n\n"
        "AI Sharc · PO Box 1622, Coppell, TX 75019\n"
    )
    get_mailer().send(to, subject, text)


def send_purchase_receipt_email(to, base_url):
    subject = "Your AI Sharc Final Report Card is ready"
    text = (
        "Thank you — your Final Report Card is ready.\n\n"
        f"Sign in to your dashboard to view it and download the PDF:\n"
        f"{base_url}/dashboard\n\n"
        "Your Final card includes 3 months of monitoring: each month we re-scan\n"
        "your site and email you if your grade changes. You can cancel any time\n"
        "from your dashboard.\n\n"
        "AI Sharc · PO Box 1622, Coppell, TX 75019\n"
    )
    get_mailer().send(to, subject, text)


def send_grade_change_email(to, domain, old_grade, new_grade, card_url):
    subject = f"Your AI Sharc grade changed: {old_grade} to {new_grade}"
    direction = "up" if new_grade > old_grade else "down"
    text = (
        f"Your monthly re-scan of {domain} found a change: your grade moved "
        f"{direction}, from {old_grade} to {new_grade}.\n\n"
        f"View your updated card:\n{card_url}\n\n"
        "AI Sharc · PO Box 1622, Coppell, TX 75019\n"
    )
    get_mailer().send(to, subject, text)


def send_cancel_confirmation_email(to, domain):
    subject = "Your AI Sharc monitoring is canceled"
    text = (
        "This confirms you canceled monitoring for your AI Sharc Final Report "
        f"Card ({domain}).\n\n"
        "Your Final Report Card stays available in your dashboard, and your "
        "re-check\nwindow terms are unchanged. If this wasn't you, contact us "
        "right away.\n\n"
        "AI Sharc · PO Box 1622, Coppell, TX 75019\n"
    )
    get_mailer().send(to, subject, text)


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
