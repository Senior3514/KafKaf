import xml.etree.ElementTree as ET

from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.net_utils import TTLCache, get_with_retry

MAX_ITEMS = 5
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_cache = TTLCache(ttl_seconds=300)  # feeds update at most every few minutes in practice


class RssSkill(Skill):
    name = "rss"
    description = "Fetch and list the latest items from an RSS/Atom feed URL."

    async def run(self, arg: str) -> str:
        url = arg.strip()
        if not url.startswith(("http://", "https://")):
            return "error: expected a feed URL starting with http:// or https://"

        cached = _cache.get(url)
        if cached is not None:
            return cached

        response = await get_with_retry(
            url, headers={"User-Agent": "KafKaf/0.1 (+https://github.com/Senior3514/KafKaf)"}
        )
        response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            return f"error: could not parse feed: {exc}"

        items = []
        for item in root.findall(".//item")[:MAX_ITEMS]:  # RSS 2.0
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if title:
                items.append(f"- {title} — {link}")

        if not items:  # Atom
            for entry in root.findall(".//atom:entry", _ATOM_NS)[:MAX_ITEMS]:
                title = (entry.findtext("atom:title", namespaces=_ATOM_NS) or "").strip()
                link_el = entry.find("atom:link", _ATOM_NS)
                link = link_el.get("href", "") if link_el is not None else ""
                if title:
                    items.append(f"- {title} — {link}")

        result = "\n".join(items) if items else "no items found in feed"
        _cache.set(url, result)
        return result
