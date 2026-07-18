"""Read-only rendering of JS-heavy pages via a locked-down headless browser
— distinct from web_fetch, which only does a raw HTTP GET and can't render
client-side-rendered content. Optional 'browser' extra (playwright),
lazily imported so the base install stays light — same pattern as
'own'/torch and mcp.

Deliberately narrow: never clicks, fills a form, or submits anything —
those Playwright APIs are simply never called. The one real action
surface a page can still reach for is client-side navigation (a redirect
the page's own JS triggers, e.g. `location.href = ...` on a timer) — the
content is captured the instant the initial `goto()` resolves, with no
artificial delay that would give a delayed redirect a window to fire, and
`page.route()` blocks any main-frame navigation request from that instant
on as a backstop against a near-zero-delay one racing the capture.
Redirects that happen *during* the initial load itself (http -> https, a
URL shortener's 30x chain) are the normal result of the one navigation
the caller asked for, and are allowed through — `goto()` only resolves
once that chain has settled.
"""

from kafkaf.core.skills.base import Skill

MAX_CHARS = 4000
_TIMEOUT_MS = 15000


class BrowserRenderSkill(Skill):
    name = "browser_render"
    description = (
        "Render a URL in a real, JS-executing browser and return its visible text — "
        "for JS-heavy pages web_fetch can't read (it only does a raw HTTP fetch). "
        "Read-only: never clicks, fills forms, or follows a page-triggered redirect "
        "away from the given URL. Usage: a full URL starting with http:// or https://."
    )

    async def run(self, arg: str) -> str:
        url = arg.strip()
        if not url.startswith(("http://", "https://")):
            return "error: expected a full URL starting with http:// or https://"

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError:
            return (
                "error: the browser_render skill needs the optional 'browser' extra: "
                'run pip install -e ".[browser]" then `playwright install chromium`.'
            )

        initial_load_done = False

        async def block_post_load_navigation(route):
            request = route.request
            if (
                initial_load_done
                and request.is_navigation_request()
                and request.frame.parent_frame is None
            ):
                await route.abort()
            else:
                await route.continue_()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    context = await browser.new_context(accept_downloads=False)
                    page = await context.new_page()
                    await page.route("**/*", block_post_load_navigation)
                    await page.goto(url, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
                    initial_load_done = True
                    text = await page.inner_text("body")
                finally:
                    await browser.close()
        except Exception as exc:
            return f"error: could not render {url!r}: {exc}"

        text = " ".join(text.split())
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "... [truncated]"
        return text or "(no visible text content)"
