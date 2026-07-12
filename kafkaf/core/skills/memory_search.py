from kafkaf.core.enrichment import store
from kafkaf.core.skills.base import Skill


class MemorySearchSkill(Skill):
    name = "memory_search"
    description = "Search what KafKaf's own model has already been taught, by keyword."

    async def run(self, arg: str) -> str:
        query = arg.strip()
        if not query:
            return "error: empty query"

        results = store.search_examples(query)
        if not results:
            return "nothing found in the corpus for that query"

        return "\n".join(f"- [{r['topic']}] {r['completion'][:200]}" for r in results)
