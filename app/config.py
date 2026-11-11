# AI Sharc — app configuration. Secrets come from environment variables only.
import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Settings:
    def __init__(self):
        self.database_url = os.environ.get("DATABASE_URL", "sqlite:///./aisharc.db")
        self.base_url = os.environ.get("BASE_URL", "https://aisharc.com")
        # mailer backend: console | smtp | sendgrid
        self.mailer = os.environ.get("MAILER", "console")
        self.mail_from = os.environ.get("MAIL_FROM", "cards@aisharc.com")
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = _int("SMTP_PORT", 587)
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.sendgrid_api_key = os.environ.get("SENDGRID_API_KEY", "")
        self.verify_token_ttl_minutes = _int("VERIFY_TOKEN_TTL_MINUTES", 30)
        self.card_session_ttl_seconds = _int("CARD_SESSION_TTL_SECONDS", 7 * 24 * 3600)
        self.scan_timeout_seconds = _int("SCAN_TIMEOUT_SECONDS", 10)
        self.card_view_limit = _int("CARD_VIEW_LIMIT", 10)
        self.submit_rate_per_ip_hour = _int("SUBMIT_RATE_PER_IP_HOUR", 5)
        self.submit_rate_per_email_hour = _int("SUBMIT_RATE_PER_EMAIL_HOUR", 3)
        # Cookie/redirect signing key. MUST be set in production; a random
        # ephemeral key is generated otherwise (sessions reset on restart).
        self.secret_key = os.environ.get("SECRET_KEY", "")


settings = Settings()
