import asyncio
import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from .brief import parse_brief
from .debate import run_debate
from .report import render

load_dotenv()

app = typer.Typer(help="Agora — run autonomous multi-agent debates from a markdown brief.")


@app.command()
def main(
    brief_path: Path = typer.Argument(..., help="Path to the brief markdown file"),
    rounds: int = typer.Option(None, "--rounds", "-r", help="Override number of rounds (default: from brief or 2)"),
    output: Path = typer.Option(Path("output"), "--output", "-o", help="Directory to write the report"),
    model: str = typer.Option(None, "--model", "-m", help="Claude model to use"),
):
    if not brief_path.exists():
        typer.echo(f"Error: brief not found: {brief_path}", err=True)
        raise typer.Exit(1)

    resolved_model = model or os.environ.get("AGORA_MODEL", "claude-opus-4-6")

    brief = parse_brief(brief_path)

    if rounds is not None:
        brief.rounds = rounds

    typer.echo(f"Agora: {brief.title}")
    typer.echo(f"Participants: {', '.join(p.role for p in brief.personas)}")
    typer.echo(f"Rounds: {brief.rounds}  Model: {resolved_model}")
    typer.echo("")

    def progress(msg: str):
        typer.echo(f"  {msg}")

    transcript = asyncio.run(run_debate(brief, resolved_model, progress_callback=progress))

    report_path = render(transcript, resolved_model, output)
    typer.echo(f"\nReport written to: {report_path}")
