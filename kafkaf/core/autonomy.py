"""Named autonomy tiers — one legible dial (`KAFKAF_AUTONOMY_LEVEL`) instead
of remembering which combination of individual flags adds up to how much
KafKaf can do without a human approving each step.

Percent framing (used in docs/SETUP.md) is approximate, not a literal
0-100 slider: named tiers are more legible and harder to misconfigure than
a raw number, while still giving predictable, granular control. A future
tier unlocks once code execution has a real, human-gated sandbox — see
docs/ROADMAP.md's Phase 9/10 entries for why that isn't "autonomous" yet.
"""

from kafkaf.core.config import settings

TIERS = ("observe", "assisted", "autonomous")

DESCRIPTIONS: dict[str, str] = {
    "observe": "Chat only. No tool use, no unattended growth loop. ~0% autonomy.",
    "assisted": "Skills (tools) available per turn, but autopilot must be "
    "started explicitly (--no-autopilot is implied). ~50% autonomy.",
    "autonomous": "Skills available, and autopilot runs unattended by default. "
    "~100% of what's safely shippable today.",
}


def skills_allowed(level: str | None = None) -> bool:
    return (level or settings.autonomy_level) != "observe"


def autopilot_default_on(level: str | None = None) -> bool:
    return (level or settings.autonomy_level) == "autonomous"


# A second, independent dial — see Settings.write_skills_mode and
# core/skills/loop.py. autonomy_level above gates whether skills run at
# all; this gates the write-capable subset (Skill.read_only is False)
# specifically, once skills are already allowed.
WRITE_SKILLS_MODES = ("manual", "assisted", "autonomous")

WRITE_SKILLS_DESCRIPTIONS: dict[str, str] = {
    "manual": "Write-capable skills (files, journal, identity, reminders, schedule) "
    "are not executed — read-only skills are unaffected.",
    "assisted": "Write-capable skills run normally, but are logged under a distinct "
    "audit event type for easy review.",
    "autonomous": "Write-capable skills run exactly like any other skill. Default.",
}
