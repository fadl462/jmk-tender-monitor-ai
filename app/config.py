import os


class Settings:
    MIN_MATCH_SCORE = int(os.environ.get("MIN_MATCH_SCORE", "40"))
    MIN_GHANA_JOB_RESULTS = int(os.environ.get("MIN_GHANA_JOB_RESULTS", "5"))
    FEED_WINDOW_DAYS = int(os.environ.get("FEED_WINDOW_DAYS", "30"))

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    DIGEST_FROM = os.environ.get("DIGEST_FROM", "")
    DIGEST_RECIPIENTS = os.environ.get("DIGEST_RECIPIENTS", "")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

    CRON_SECRET = os.environ.get("CRON_SECRET", "")


settings = Settings()
