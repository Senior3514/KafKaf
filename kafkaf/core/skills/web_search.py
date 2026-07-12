"""Web search with no API key required, via DuckDuckGo's HTML-only endpoint
(the same approach many open-source agent tools use to avoid a paid search
API). Depends on DuckDuckGo's HTML structure staying roughly stable — if
results ever come back empty, that's the first thing to check.
"""

import html
import re

import httpx

from kafkaf.core.skills.base import Skill

_RESULT_RE = re.compile(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', re.DOTALL)
_SNIPPET_RE = re.compile(r'<a class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


class WebSearchSkill(Skill):
    name = "web_search"
    description = "Search the web for a query; returns a few result titles, links, and snippets."

    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def run(self, arg: str) -> str:
        query = arg.strip()
        if not query:
            return "error: empty query"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "KafKaf/0.1 (+https://github.com/Senior3514/KafKaf)"},
            )
            response.raise_for_status()

        titles = _RESULT_RE.findall(response.text)
        snippets = _SNIPPET_RE.findall(response.text)

        if not titles:
            return "no results found"

        lines = []
        for i, (link, title) in enumerate(titles[: self.max_results]):
            snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
            lines.append(f"{i + 1}. {_strip_tags(title)} — {link}\n   {snippet}")
        return "\n".join(lines)
