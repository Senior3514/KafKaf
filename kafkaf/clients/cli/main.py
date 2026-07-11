import uuid

import httpx
import typer

app = typer.Typer(help="KafKaf CLI — talk to your local KafKaf instance.")

DEFAULT_URL = "http://localhost:8420"


def _send(url: str, session_id: str, persona: str, message: str) -> str:
    response = httpx.post(
        f"{url}/chat",
        json={"message": message, "session_id": session_id, "persona": persona},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["reply"]


@app.command()
def chat(
    message: str,
    session: str = typer.Option(None, help="Session id to keep conversation context."),
    persona: str = typer.Option("default", help="Persona to talk to."),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Send a single message to KafKaf and print the reply."""
    session_id = session or str(uuid.uuid4())
    typer.echo(_send(url, session_id, persona, message))


@app.command()
def repl(
    session: str = typer.Option(None, help="Session id to keep conversation context."),
    persona: str = typer.Option("default", help="Persona to talk to."),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Start an interactive terminal chat session. Type 'exit' or Ctrl+C/Ctrl+D to leave."""
    session_id = session or str(uuid.uuid4())
    typer.echo(f"KafKaf ({persona}) — session {session_id}. Type 'exit' to leave.\n")

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
            reply = _send(url, session_id, persona, message)
        except httpx.HTTPError as exc:
            typer.echo(f"error: {exc}")
            continue

        typer.echo(f"kafkaf> {reply}\n")


if __name__ == "__main__":
    app()
