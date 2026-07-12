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
    return response.json()["reply"]


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


if __name__ == "__main__":
    app()
