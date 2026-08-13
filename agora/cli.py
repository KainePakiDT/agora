import asyncio
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from .brief import parse_brief
from .debate import run_debate
from .report import render

app = typer.Typer(help="Agora — run autonomous multi-agent debates from a markdown brief.")

_DEBATE_COMMAND_TEMPLATE = """\
---
description: Debate two options using the agora multi-agent tool, seeded with the current conversation context
---

The user wants to run a structured debate. Their input: **$ARGUMENTS**

Follow these steps exactly:

## Step 1 — Parse the two options

Extract Option A and Option B from the arguments. They may be separated by "vs", "versus", "or", a comma, or a slash. If you cannot identify two distinct options, stop and ask the user to clarify with the format: `Option A vs Option B`.

## Step 2 — Summarise the conversation context

Review the conversation history above this command. Write a concise 3–6 sentence background context that captures:
- What problem or decision is being discussed
- Any constraints, requirements, or goals that were mentioned
- Relevant technical, business, or organisational details

If the conversation has no useful context (e.g. this was the first message), write a short neutral description of the decision instead.

## Step 3 — Write the brief file

Write a brief markdown file to `__BRIEFS_DIR__/debate_current.md` with **exactly** this structure (substituting the placeholders):

```
# Brief: {Option A} vs {Option B}

## Topic
Should we go with {Option A} over {Option B}?

## Context
{conversation context summary from Step 2}

## Personas
- For: {Option A} Advocate — argues strongly in favour of {Option A} and its specific benefits
- Against: {Option B} Advocate — argues strongly in favour of {Option B} as the better choice
- Neutral: Decision Analyst — weighs trade-offs objectively and seeks the best practical outcome

## Rounds
2
```

## Step 4 — Run agora

Run the following command and wait for it to complete (it may take a minute or two):

```bash
"__AGORA_BIN__" "__BRIEFS_DIR__/debate_current.md" --output "__OUTPUT_DIR__"
```

## Step 5 — Display the synthesis

After agora finishes, find the most recently modified file in `__OUTPUT_DIR__` and read it. Display the full contents of the report to the user.
"""


@app.command()
def main(
    brief_path: Path = typer.Argument(..., help="Path to the brief markdown file"),
    rounds: int = typer.Option(None, "--rounds", "-r", help="Override number of rounds (default: from brief or 2)"),
    output: Path = typer.Option(Path("output"), "--output", "-o", help="Directory to write the report"),
    model: str = typer.Option(None, "--model", "-m", help="Claude model to pass to the claude CLI"),
):
    if not brief_path.exists():
        typer.echo(f"Error: brief not found: {brief_path}", err=True)
        raise typer.Exit(1)

    resolved_model = model or os.environ.get("AGORA_MODEL")

    brief = parse_brief(brief_path)

    if rounds is not None:
        brief.rounds = rounds

    typer.echo(f"Agora: {brief.title}")
    typer.echo(f"Participants: {', '.join(p.role for p in brief.personas)}")
    model_label = resolved_model or "claude CLI default"
    typer.echo(f"Rounds: {brief.rounds}  Model: {model_label}")
    typer.echo("")

    def progress(msg: str):
        typer.echo(f"  {msg}")

    transcript = asyncio.run(run_debate(brief, resolved_model, progress_callback=progress))

    report_path = render(transcript, model_label, output)
    typer.echo(f"\nReport written to: {report_path}")


def setup():
    """Install the /debate Claude Code slash command."""
    agora_bin = shutil.which("agora")
    if agora_bin is None:
        print("Error: could not find agora on PATH.", file=sys.stderr)
        sys.exit(1)

    agora_bin_posix = Path(agora_bin).as_posix()

    workspace = Path.home() / ".agora"
    briefs_dir = workspace / "briefs"
    output_dir = workspace / "output"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    briefs_posix = briefs_dir.as_posix()
    output_posix = output_dir.as_posix()

    commands_dir = Path.home() / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    content = (
        _DEBATE_COMMAND_TEMPLATE
        .replace("__AGORA_BIN__", agora_bin_posix)
        .replace("__BRIEFS_DIR__", briefs_posix)
        .replace("__OUTPUT_DIR__", output_posix)
    )

    debate_md = commands_dir / "debate.md"
    debate_md.write_text(content, encoding="utf-8")

    print(f"Installed: {debate_md}")
    print(f"Briefs:    {briefs_dir}")
    print(f"Output:    {output_dir}")

    scripts_dir = Path(agora_bin).parent
    if platform.system() == "Windows":
        ps_cmd = (
            f'[Environment]::SetEnvironmentVariable('
            f'"PATH", "{scripts_dir};" + '
            f'[Environment]::GetEnvironmentVariable("PATH", "User"), "User")'
        )
        result = subprocess.run(["powershell", "-Command", ps_cmd])
        if result.returncode == 0:
            print(f"Added to PATH: {scripts_dir}")
            print("Open a new terminal for the PATH change to take effect.")
        else:
            print(f"Could not update PATH automatically. Add this manually: {scripts_dir}")
    else:
        print(f"Add this to your PATH: {scripts_dir}")


def update():
    """Pull latest changes from the git repo and reinstall."""
    source_dir = Path(__file__).parent.parent

    if not (source_dir / ".git").exists():
        print("Error: agora does not appear to be installed from a git clone.", file=sys.stderr)
        sys.exit(1)

    pyproject_before = (source_dir / "pyproject.toml").read_text(encoding="utf-8")

    print("Pulling latest changes...")
    result = subprocess.run(["git", "pull"], cwd=source_dir)
    if result.returncode != 0:
        print("Error: git pull failed.", file=sys.stderr)
        sys.exit(1)

    pyproject_after = (source_dir / "pyproject.toml").read_text(encoding="utf-8")
    if pyproject_after != pyproject_before:
        print("pyproject.toml changed — run 'uv pip install -e .' to pick up new dependencies or entry points.")
    else:
        print("Done.")
