import uuid

import httpx
import typer

app = typer.Typer(help="KafKaf CLI — talk to your local KafKaf instance.")

DEFAULT_URL = "http://localhost:8420"


def _send(
    url: str,
    session_id: str,
    persona: str,
    message: str,
    brain: str | None,
    council: bool,
    skills: bool,
) -> str:
    response = httpx.post(
        f"{url}/chat",
        json={
            "message": message,
            "session_id": session_id,
            "persona": persona,
            "brain": brain,
            "council": council,
            "skills": skills,
        },
        timeout=180.0,
    )
    if response.is_error:
        detail = response.json().get("detail", response.text) if response.text else response.text
        raise httpx.HTTPStatusError(detail, request=response.request, response=response)
    data = response.json()
    if data.get("pending_approval"):
        # run_code/browser_automate always pause for a live approve/deny
        # click — only the web GUI's chat bubble has that button today.
        pending = data["pending_approval"]
        return (
            f"[paused: {pending['skill_name']!r} needs a human approval click before it can "
            f"run — approve/deny isn't available from the CLI yet, use the web GUI for this "
            f"turn (approval #{pending['approval_id']})]"
        )
    return data["reply"]


@app.command()
def chat(
    message: str,
    session: str = typer.Option(None, help="Session id to keep conversation context."),
    persona: str = typer.Option("default", help="Persona to talk to."),
    brain: str = typer.Option(
        None, help="Brain override, e.g. 'own' or 'ollama:llama3'. Defaults to the persona's."
    ),
    council: bool = typer.Option(
        False, "--council", help="Fan out to every KAFKAF_COUNCIL_BRAINS brain and synthesize one answer."
    ),
    skills: bool = typer.Option(
        False, "--skills", help="Let the brain use tools (web search, calculator, files, ...). Ignored with --council."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Send a single message to KafKaf and print the reply."""
    session_id = session or str(uuid.uuid4())
    typer.echo(_send(url, session_id, persona, message, brain, council, skills))


@app.command()
def repl(
    session: str = typer.Option(None, help="Session id to keep conversation context."),
    persona: str = typer.Option("default", help="Persona to talk to."),
    brain: str = typer.Option(
        None, help="Brain override, e.g. 'own' or 'ollama:llama3'. Defaults to the persona's."
    ),
    council: bool = typer.Option(
        False, "--council", help="Fan out to every KAFKAF_COUNCIL_BRAINS brain and synthesize one answer."
    ),
    skills: bool = typer.Option(
        False, "--skills", help="Let the brain use tools (web search, calculator, files, ...). Ignored with --council."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Start an interactive terminal chat session. Type 'exit' or Ctrl+C/Ctrl+D to leave."""
    session_id = session or str(uuid.uuid4())
    label = "council" if council else (brain or persona)
    if skills and not council:
        label += "+skills"
    typer.echo(f"KafKaf ({label}) — session {session_id}. Type 'exit' to leave.\n")

    while True:
        try:
            message = typer.prompt("you", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nbye.")
            break

        if message.strip().lower() in {"exit", "quit"}:
            typer.echo("bye.")
            break

        try:
            reply = _send(url, session_id, persona, message, brain, council, skills)
        except httpx.HTTPError as exc:
            typer.echo(f"error: {exc}")
            continue

        typer.echo(f"kafkaf> {reply}\n")


@app.command()
def audit(
    limit: int = typer.Option(50, help="How many recent events to show."),
    event_type: str = typer.Option(
        None, help="Filter to one event type, e.g. 'chat', 'skill', 'autopilot_teach'."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Show recent audit log events — what KafKaf actually did, and when."""
    params = {"limit": limit}
    if event_type:
        params["event_type"] = event_type
    response = httpx.get(f"{url}/audit", params=params, timeout=30.0)
    response.raise_for_status()
    events = response.json()
    if not events:
        typer.echo("no audit events yet")
        return
    for event in events:
        actor = f" ({event['actor']})" if event["actor"] else ""
        duration = f" [{event['duration_ms']}ms]" if event["duration_ms"] is not None else ""
        typer.echo(f"[{event['created_at']}] {event['event_type']}{actor}{duration}: {event['summary']}")


@app.command()
def autonomy(
    set_level: str = typer.Option(
        None, "--set", help="Change the autonomy level (observe/assisted/autonomous) for the running backend."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Show, or change, the current autonomy level and what it unlocks."""
    if set_level:
        response = httpx.post(f"{url}/autonomy", json={"level": set_level}, timeout=30.0)
        if response.is_error:
            detail = response.json().get("detail", response.text) if response.text else response.text
            raise httpx.HTTPStatusError(detail, request=response.request, response=response)
    else:
        response = httpx.get(f"{url}/autonomy", timeout=30.0)
        response.raise_for_status()
    info = response.json()
    typer.echo(f"level: {info['level']}")
    typer.echo(f"skills allowed: {info['skills_allowed']}")
    typer.echo(info["description"])


@app.command()
def write_skills(
    set_mode: str = typer.Option(
        None, "--set", help="Change the write-skills mode (manual/assisted/autonomous) for the running backend."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Show, or change, the write-skills mode — a second, independent dial
    from autonomy that gates write-capable skills (files, journal,
    identity, reminders, schedule) specifically, once skills are already
    allowed at all."""
    if set_mode:
        response = httpx.post(f"{url}/skills/write-mode", json={"mode": set_mode}, timeout=30.0)
        if response.is_error:
            detail = response.json().get("detail", response.text) if response.text else response.text
            raise httpx.HTTPStatusError(detail, request=response.request, response=response)
    else:
        response = httpx.get(f"{url}/skills/write-mode", timeout=30.0)
        response.raise_for_status()
    info = response.json()
    typer.echo(f"mode: {info['mode']}")
    typer.echo(info["description"])


@app.command()
def workspace(
    set_path: str = typer.Option(
        None, "--set", help="Point filesystem-touching skills (files, document_search, journal) at this directory."
    ),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Show, or change, the directory skills are sandboxed to — the same
    "one directory you choose" model as Claude Code's own cwd."""
    if set_path:
        response = httpx.post(f"{url}/skills/workspace", json={"path": set_path}, timeout=30.0)
        if response.is_error:
            detail = response.json().get("detail", response.text) if response.text else response.text
            raise httpx.HTTPStatusError(detail, request=response.request, response=response)
        typer.echo(f"workspace: {response.json()['skills_workspace_dir']}")
    else:
        response = httpx.get(f"{url}/status", timeout=30.0)
        response.raise_for_status()
        typer.echo(f"workspace: {response.json()['skills_workspace_dir']}")


if __name__ == "__main__":
    app()
