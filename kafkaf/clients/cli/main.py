import uuid

import httpx
import typer

app = typer.Typer(help="KafKaf CLI — talk to your local KafKaf instance.")

DEFAULT_URL = "http://localhost:8420"


@app.command()
def chat(
    message: str,
    session: str = typer.Option(None, help="Session id to keep conversation context."),
    persona: str = typer.Option("default", help="Persona to talk to."),
    url: str = typer.Option(DEFAULT_URL, help="KafKaf backend URL."),
) -> None:
    """Send a single message to KafKaf and print the reply."""
    session_id = session or str(uuid.uuid4())
    response = httpx.post(
        f"{url}/chat",
        json={"message": message, "session_id": session_id, "persona": persona},
        timeout=120.0,
    )
    response.raise_for_status()
    typer.echo(response.json()["reply"])


if __name__ == "__main__":
    app()
