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
        # Stage 3 — monetization. All secrets env-only; no Stripe key means
        # checkout routes return a "billing not configured" page (dev safe).
        self.stripe_api_key = os.environ.get("STRIPE_API_KEY", "")
        self.stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.price_final_intro_cents = _int("PRICE_FINAL_INTRO_CENTS", 9900)
        self.price_final_regular_cents = _int("PRICE_FINAL_REGULAR_CENTS", 14900)
        self.price_monitoring_intro_cents = _int("PRICE_MONITORING_INTRO_CENTS", 2500)
        self.price_monitoring_regular_cents = _int("PRICE_MONITORING_REGULAR_CENTS", 3000)
        # Introductory Final price applies to the first 500 firms (locked pricing).
        self.intro_firm_limit = _int("INTRO_FIRM_LIMIT", 500)
        # Unlimited re-checks within 60 days of the original card (spec v1.22).
        self.recheck_window_days = _int("RECHECK_WINDOW_DAYS", 60)
        # Monthly monitoring job cadence and scan spacing, in days/hours.
        self.monitoring_scan_interval_days = _int("MONITORING_SCAN_INTERVAL_DAYS", 30)
        self.monitoring_poll_seconds = _int("MONITORING_POLL_SECONDS", 3600)
        # Admin reconciliation endpoint token (webhook-missed recovery). Env only.
        self.admin_token = os.environ.get("ADMIN_TOKEN", "")
        self.stripe_test_mode = os.environ.get("STRIPE_TEST_MODE", "") == "1"


settings = Settings()
