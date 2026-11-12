# AI Sharc — Chromium path resolution for the PDF exporter (container override).
import importlib
import os


def test_chromium_path_env_override(monkeypatch):
    """The Chromium binary path is env-overridable (Railway/Docker apt install),
    with the local-dev default kept."""
    import app.pdf as pdf

    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
    reloaded = importlib.reload(pdf)
    assert reloaded.CHROMIUM == "/usr/bin/chromium"

    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", raising=False)
    reloaded = importlib.reload(pdf)
    assert reloaded.CHROMIUM == "/usr/local/bin/chromium"
    importlib.reload(pdf)  # restore original module state
