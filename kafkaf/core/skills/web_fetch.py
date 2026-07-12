import html
import re

import httpx

from kafkaf.core.skills.base import Skill

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")

MAX_CHARS = 4000


class WebFetchSkill(Skill):
    name = "web_fetch"
    description = "Fetch a URL and return its readable text content (truncated)."

    async def run(self, arg: str) -> str:
        url = arg.strip()
        if not url.startswith(("http://", "https://")):
            return "error: expected a full URL starting with http:// or https://"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                url, headers={"User-Agent": "KafKaf/0.1 (+https://github.com/Senior3514/KafKaf)"}
            )
            response.raise_for_status()

        text = _SCRIPT_STYLE_RE.sub(" ", response.text)
        text = _TAG_RE.sub(" ", text)
        text = html.unescape(text)
        text = _WHITESPACE_RE.sub(" ", text)
        text = _BLANK_LINES_RE.sub("\n\n", text).strip()

        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "... [truncated]"
        return text or "(no readable text content)"
