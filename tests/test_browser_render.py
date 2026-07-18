"""browser_render is optional (the 'browser' extra, playwright) and needs
a real chromium binary on top of the pip package (`playwright install
chromium`) — same two-part-optional-dependency shape as own_model_brain's
torch. The safety-critical behavior (never captures/navigates to a
page-triggered redirect target) is proven end-to-end here against a real
local HTTP server whenever a working chromium is available; environments
without one (no playwright installed, or the pip package present but no
browser binary — e.g. a bare CI image) skip cleanly, mirroring
`torch = pytest.importorskip("torch")` elsewhere in this test suite.
"""

import http.server
import sys
import threading

import pytest
import pytest_asyncio

from kafkaf.core.skills.browser_render import BrowserRenderSkill

REDIRECT_PAGE = b"""<!doctype html><html><body>
<h1>original page content</h1>
<script>setTimeout(() => { location.href = '/evil'; }, 50);</script>
</body></html>"""

EVIL_PAGE = b"""<!doctype html><html><body><h1>EVIL PAGE - should never be seen</h1></body></html>"""

JS_RENDERED_PAGE = b"""<!doctype html><html><body id="content">
<script>document.getElementById('content').innerText = 'rendered via JS, not raw HTML';</script>
</body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = {"/redirect-test": REDIRECT_PAGE, "/evil": EVIL_PAGE, "/js-test": JS_RENDERED_PAGE}.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
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


class TestBrowserRender:
    @pytest.mark.asyncio
    async def test_rejects_non_url_input(self):
        result = await BrowserRenderSkill().run("not a url")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_missing_playwright_gives_clean_error(self, monkeypatch):
        # Standard trick for simulating "package not installed": setting a
        # module to None in sys.modules makes a future `import` of that
        # exact name raise ImportError, without touching real import
        # machinery for anything else.
        monkeypatch.setitem(sys.modules, "playwright.async_api", None)
        result = await BrowserRenderSkill().run("https://example.com")
        assert result.startswith("error:")
        assert "browser" in result

    @pytest.mark.asyncio
    async def test_renders_js_content_and_blocks_page_triggered_redirect(
        self, chromium_available, local_server
    ):
        result = await BrowserRenderSkill().run(f"http://127.0.0.1:{local_server}/redirect-test")
        assert "original page content" in result
        assert "EVIL PAGE" not in result

    @pytest.mark.asyncio
    async def test_actually_executes_javascript(self, chromium_available, local_server):
        result = await BrowserRenderSkill().run(f"http://127.0.0.1:{local_server}/js-test")
        assert "rendered via JS, not raw HTML" in result
