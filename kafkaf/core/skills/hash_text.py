import hashlib

from kafkaf.core.skills.base import Skill

_ALGORITHMS = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}


class HashTextSkill(Skill):
    name = "hash_text"
    description = (
        "Compute a hash of text. Usage: '<algorithm> <text>', algorithm one of "
        "md5, sha1, sha256 (default sha256)."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()
        if not arg:
            return "error: empty input"

        first_word, _, rest = arg.partition(" ")
        if first_word.lower() in _ALGORITHMS:
            algorithm, text = first_word.lower(), rest
        else:
            algorithm, text = "sha256", arg

        if not text:
            return "error: no text to hash"

        return _ALGORITHMS[algorithm](text.encode("utf-8")).hexdigest()
