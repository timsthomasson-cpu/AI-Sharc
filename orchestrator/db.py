"""Database connection for the orchestrator.

The connection string comes from the DATABASE_URL environment variable (a Railway secret), and is never
written to a file or a log. Use the test database (Test AI Sharc Orchestrator) until the test checks out;
AI Sharc Orchestrator East is the live database.
"""
import os


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (the Supabase connection string, kept as a Railway secret).")
    import psycopg  # imported here so the offline tools and tests run without it
    return psycopg.connect(url, autocommit=False)
