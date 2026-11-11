# AI Sharc — PDF export of a Final Report Card via Playwright + system Chromium.
# Chromium binary is /usr/local/bin/chromium (do NOT download managed browsers).
import logging
import os
import tempfile

log = logging.getLogger("aisharc.pdf")

CHROMIUM = "/usr/local/bin/chromium"


def render_pdf(html, out_path):
    """Render a complete HTML document to PDF. Synchronous; returns out_path.
    Raises if the export fails — callers show a generic download error."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(path=out_path, format="A4", print_background=True,
                     margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
        finally:
            browser.close()
    return out_path


def card_pdf_bytes(html):
    """Render to a temp file and return the bytes (for FastAPI responses)."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        render_pdf(html, path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def pdf_pdf_document(html_doc):
    """Full document wrapper: embeds the card in a print-friendly page that
    loads no external assets (PDFs must render offline)."""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>AI Sharc Final Report Card</title>
<style>
body{{font-family:'Liberation Sans',Arial,sans-serif;color:#123B63;margin:0;padding:24px;font-size:11pt}}
.report-card{{border:2px solid #123B63;border-radius:12px;padding:16px;max-width:100%}}
.rc-head{{display:flex;align-items:center;gap:12px;border-bottom:1px solid #ccc;padding-bottom:10px;margin-bottom:10px}}
.grade{{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:8px;font-weight:800;color:#fff;background:#123B63}}
.rc-find{{border-left:3px solid #ccc;padding:6px 10px;margin-bottom:8px;background:#f5f8fb}}
.rc-find h4{{margin:0 0 2px;font-size:10.5pt}} .rc-find p{{margin:0;font-size:9.5pt;color:#43566b}}
.rc-src{{font-size:8.5pt;color:#5b7186;margin-top:2px}}
h3,h4{{margin:0}} .note{{color:#5b7186;font-size:9pt}}
</style></head><body>{html_doc}</body></html>'''
