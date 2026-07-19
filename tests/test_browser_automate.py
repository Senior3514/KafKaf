"""browser_automate mirrors browser_render's two-part-optional-dependency
shape (playwright pip package + a real chromium binary) — see
test_browser_render.py's module docstring. The write-capable behaviors
(click actually fires, fill actually sets the field, submit actually
POSTs) are proven end-to-end against a real local HTTP server whenever a
working chromium is available; environments without one skip cleanly."""

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import pytest
import pytest_asyncio

from kafkaf.core.skills.browser_automate import BrowserAutomateSkill

CLICK_PAGE = b"""<!doctype html><html><body><a id="target" href="/after-click">go</a></body></html>"""
AFTER_CLICK_PAGE = b"""<!doctype html><html><body><h1>clicked successfully</h1></body></html>"""
FILL_PAGE = b"""<!doctype html><html><body>
<input id="name-field" oninput="document.getElementById('preview').textContent = this.value">
<span id="preview">(empty)</span>
</body></html>"""
FORM_PAGE = b"""<!doctype html><html><body>
<form method="POST" action="/form-submit">
<input id="name-field" name="name" value="default value">
<button id="submit-btn" type="submit">Go</button>
</form>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {
            "/click-test": CLICK_PAGE,
            "/after-click": AFTER_CLICK_PAGE,
            "/fill-test": FILL_PAGE,
            "/form-test": FORM_PAGE,
        }.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/form-submit":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        submitted = parse_qs(self.rfile.read(length).decode())
        name = submitted.get("name", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<!doctype html><html><body><p>submitted: {name}</p></body></html>".encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()


@pytest_asyncio.fixture
async def chromium_available():
    playwright_module = pytest.importorskip("playwright.async_api")
    try:
        async with playwright_module.async_playwright() as p:
            browser = await p.chromium.launch()
            await browser.close()
    except Exception as exc:
        pytest.skip(f"no working chromium binary available ('playwright install chromium'): {exc}")


class TestBrowserAutomateGrammar:
    @pytest.mark.asyncio
    async def test_rejects_unparseable_action(self):
        result = await BrowserAutomateSkill().run("do something weird")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_rejects_non_url(self):
        result = await BrowserAutomateSkill().run("goto not-a-url")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_missing_playwright_gives_clean_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "playwright.async_api", None)
        result = await BrowserAutomateSkill().run("goto https://example.com")
        assert result.startswith("error:")
        assert "browser" in result


class TestBrowserAutomateLive:
    @pytest.mark.asyncio
    async def test_goto_returns_page_text(self, chromium_available, local_server):
        result = await BrowserAutomateSkill().run(f"goto http://127.0.0.1:{local_server}/click-test")
        assert "go" in result

    @pytest.mark.asyncio
    async def test_click_navigates_and_returns_new_page_text(self, chromium_available, local_server):
        result = await BrowserAutomateSkill().run(
            f"click #target on http://127.0.0.1:{local_server}/click-test"
        )
        assert "clicked successfully" in result

    @pytest.mark.asyncio
    async def test_fill_actually_sets_the_field(self, chromium_available, local_server):
        result = await BrowserAutomateSkill().run(
            f"fill #name-field with hello there on http://127.0.0.1:{local_server}/fill-test"
        )
        # The page's own live JS mirrors the typed value into visible text —
        # proving the fill actually reached the field, not just a no-op.
        assert "hello there" in result

    @pytest.mark.asyncio
    async def test_submit_posts_real_form_data(self, chromium_available, local_server):
        result = await BrowserAutomateSkill().run(
            f"submit #submit-btn on http://127.0.0.1:{local_server}/form-test"
        )
        assert "submitted: default value" in result
