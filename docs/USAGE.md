# Using KafKaf, day to day

`docs/GUIDE.md` gets KafKaf installed. This is what to do once it's
running — talking to it, teaching it, and understanding what it's
actually doing. Full reference for every option: `docs/SETUP.md`.

## Just chat

Open the web GUI (`http://<your-host>:8420`), or:

```bash
kafkaf chat "what can you help with?"
kafkaf repl                              # keeps context across messages
```

Every interface — web, CLI, desktop app, API — shares the same
conversation history per `session_id`, so switching between them mid-chat
is fine.

**Prefer a native window over a browser tab?** It's a real, already-built
desktop app, not just the web GUI in disguise — run it directly (two
separate commands, run one after the other finishes):
```bash
pip install -e ".[desktop]"
kafkaf-desktop
```
`kafkaf-desktop` opens a native OS window (no browser chrome) **and starts
its own backend automatically** — you do not also need `kafkaf-server`
running in a second window. Pick one or the other: the browser at
`http://localhost:8420` (needs `kafkaf-server` running), or this single
`kafkaf-desktop` command (needs nothing else running). See
`docs/SETUP.md#desktop-app` for pre-built executables that don't need
Python installed at all.

**Language and theme**: the web GUI's header has a language toggle
(עב/EN — switches the whole UI, never mixed Hebrew+English) and a theme
toggle (☀️ Light / 🌙 Dark / 🌅 Auto, where Auto follows the real local
sunset/sunrise, not just a fixed clock time). Both choices persist across
visits.

## Picking how it answers

Three independent choices, all combinable:

- **Persona** (tone/instructions, not a different model): `default` /
  `researcher` / `coach`. Web GUI dropdown, `kafkaf chat --persona
  researcher`, or `{"persona": "researcher"}`.
- **Brain** (which model answers): the configured default, or `own` for
  your growing private model. `kafkaf chat --brain own`, or
  `{"brain": "own"}`.
- **Council** (several models, one synthesized answer) and **skills**
  (tool use — web search, calculator, files, and more) each toggle on
  independently, and combine with each other: `kafkaf chat --council
  --skills "..."` runs every `KAFKAF_COUNCIL_BRAINS` brain through the
  tool-use loop before synthesizing. See `docs/SETUP.md#skills-giving-the-brain-real-tools`
  for the full skill list.

## Teaching your own model

Your own model (`brain: own`) starts knowing nothing — it only gets
better from what you put into it. Two ways, and they compose:

**Manually, via MCP** (Claude Desktop/Code) — `teach_fact`,
`distill_from_teacher`, `train_step`, `status`. See
`docs/SETUP.md#own-model-enrichment-mcp-server`.

**Automatically, via autopilot** — runs by default at the `autonomous`
autonomy level (see below), cycling a curriculum through a teacher model
and training periodically, no attention required. Watch it:
```bash
docker compose -f deploy/docker-compose.yml logs -f autopilot
```
Stop it anytime, gracefully, within seconds:
```bash
docker compose -f deploy/docker-compose.yml exec autopilot kafkaf-autopilot-ctl stop
```

**Calibrate your expectations honestly**: loss decreasing in `status()` or
the autopilot logs is proof the pipeline is genuinely learning — it is
not proof of a coherent conversationalist yet. A model taught a handful of
facts and trained for tens of steps will produce something close to noise;
that's expected, not broken. Quality compounds with more teaching and more
training over time, the same way it would for any specialized model
trained from scratch. See `docs/ROADMAP.md`'s vision section for why this
never turns into general intelligence no matter how long it runs, and why
that's not the point.

## Knowing what it's doing

Two commands answer "is this actually working, and what has it done":

```bash
kafkaf autonomy    # what KafKaf is currently allowed to do on its own
kafkaf audit       # what it has actually done — every chat, skill call, autopilot cycle
```

`kafkaf autonomy` reflects `KAFKAF_AUTONOMY_LEVEL` (`observe` / `assisted`
/ `autonomous` — see `docs/SETUP.md#autonomy-levels`), the single setting
that governs whether skills and autopilot are even reachable. `kafkaf
audit` is the actual record — actor, duration, and a short summary for
every event — so "what did the unattended loop do while I wasn't
watching" always has a real answer, not just a log file to grep.

## Common day-to-day commands

```bash
kafkaf chat "message"                          # one-shot
kafkaf repl                                    # interactive session
kafkaf chat --brain own "message"              # talk to your own model
kafkaf chat --council "message"                # every configured brain, synthesized
kafkaf chat --skills "message"                 # tool use
kafkaf chat --council --skills "message"       # both, combined
kafkaf audit --event-type skill                # filter the audit log
kafkaf autonomy                                # current autonomy level
./deploy/update.sh                             # pull + rebuild, same mode as installed
docker compose -f deploy/docker-compose.yml exec autopilot kafkaf-autopilot-ctl stop
```
