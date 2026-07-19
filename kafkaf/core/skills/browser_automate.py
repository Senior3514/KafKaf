"""Real, write-capable browser automation — the click/fill/submit sibling
of the read-only browser_render skill. requires_approval: it never runs
without a live human clicking approve first (see core/skills/loop.py,
core/council.py's resume_chat), and it can never be scheduled or reached
from the unattended autopilot loop (core/skills/schedule.py,
core/skills/registry.py).

Deliberately narrow scope: this is browser automation, not OS/desktop
automation — it only ever drives a fresh, isolated, headless Chromium
context via Playwright, never the user's real browser profile/cookies,
never any other application or window on the machine. One call performs
exactly one action (goto/click/fill/submit), matching the safety model
exactly: a multi-step flow needs a separate approval per step, by design.
No cross-call session/login persistence in v1 — each call is stateless,
a fresh context opened and closed per invocation.
"""

import re

from kafkaf.core.skills.base import Skill

MAX_CHARS = 4000
_TIMEOUT_MS = 15000

_GOTO_RE = re.compile(r"^goto\s+(\S+)$")
_CLICK_RE = re.compile(r"^click\s+(\S+)\s+on\s+(\S+)$")
_SUBMIT_RE = re.compile(r"^submit\s+(\S+)\s+on\s+(\S+)$")
_FILL_RE = re.compile(r"^fill\s+(\S+)\s+with\s+(.*?)\s+on\s+(\S+)$", re.DOTALL)


class BrowserAutomateSkill(Skill):
    name = "browser_automate"
    read_only = False
    requires_approval = True
    description = (
        "Perform ONE real action in an isolated, headless browser (never the user's own "
        "browser/profile), then return the resulting page text. Always pauses for a live "
        "human approval click before it runs. Usage, exactly one of: "
        "'goto <url>', 'click <selector> on <url>', 'fill <selector> with <text> on <url>', "
        "'submit <selector> on <url>' (selector/url must each be one token with no spaces)."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()
        action = self._parse(arg)
        if action is None:
            return (
                "error: expected 'goto <url>', 'click <selector> on <url>', "
                "'fill <selector> with <text> on <url>', or 'submit <selector> on <url>'"
            )
        verb, url = action["verb"], action["url"]
        if not url.startswith(("http://", "https://")):
            return "error: expected a full URL starting with http:// or https://"

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError:
            return (
                "error: the browser_automate skill needs the optional 'browser' extra: "
                'run pip install -e ".[browser]" then `playwright install chromium`.'
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    context = await browser.new_context(accept_downloads=False)
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
                    if verb == "click":
                        await page.click(action["selector"], timeout=_TIMEOUT_MS)
                    elif verb == "fill":
                        await page.fill(action["selector"], action["text"], timeout=_TIMEOUT_MS)
                    elif verb == "submit":
                        await page.click(action["selector"], timeout=_TIMEOUT_MS)
                    text = await page.inner_text("body")
                finally:
                    await browser.close()
        except Exception as exc:
            return f"error: could not perform {verb!r} on {url!r}: {exc}"

        text = " ".join(text.split())
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "... [truncated]"
        return text or "(no visible text content)"

    @staticmethod
    def _parse(arg: str) -> dict | None:
        match = _GOTO_RE.match(arg)
        if match:
            return {"verb": "goto", "url": match.group(1)}
        match = _CLICK_RE.match(arg)
        if match:
            return {"verb": "click", "selector": match.group(1), "url": match.group(2)}
        match = _SUBMIT_RE.match(arg)
        if match:
            return {"verb": "submit", "selector": match.group(1), "url": match.group(2)}
        match = _FILL_RE.match(arg)
        if match:
            return {"verb": "fill", "selector": match.group(1), "text": match.group(2), "url": match.group(3)}
        return None
