import asyncio
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from .brief import parse_brief
from .debate import run_debate
from .report import render

app = typer.Typer(help="Agora -- run autonomous multi-agent debates from a markdown brief.")

_DEBATE_COMMAND_TEMPLATE = """\
---
description: Debate two options using the agora multi-agent tool, seeded with the current conversation context
---

The user wants to run a structured debate. Their input: **$ARGUMENTS**

Follow these steps exactly:

## Step 1 -- Parse the two options

Extract Option A and Option B from the arguments. They may be separated by "vs", "versus", "or", a comma, or a slash. If you cannot identify two distinct options, stop and ask the user to clarify with the format: `Option A vs Option B`.

## Step 2 -- Summarise the conversation context

Review the conversation history above this command. Write a concise 3-6 sentence background context that captures:
- What problem or decision is being discussed
- Any constraints, requirements, or goals that were mentioned
- Relevant technical, business, or organisational details

If the conversation has no useful context (e.g. this was the first message), write a short neutral description of the decision instead.

## Step 3 -- Create a session folder and write the brief

Run this command to create a unique session folder for this debate and capture the GUID it prints:

```bash
"__PYTHON_BIN__" -c "import uuid, os; g=str(uuid.uuid4()); p='__DEBATES_DIR__/'+g; os.makedirs(p+'/output', exist_ok=True); print(g)"
```

The printed output is `{guid}`. Write a brief markdown file to `__DEBATES_DIR__/{guid}/brief.md` with **exactly** this structure (substituting the placeholders):

```
# Brief: {Option A} vs {Option B}

## Topic
Should we go with {Option A} over {Option B}?

## Context
{conversation context summary from Step 2}

## Personas
- For: {Option A} Advocate -- argues strongly in favour of {Option A} and its specific benefits
- Against: {Option B} Advocate -- argues strongly in favour of {Option B} as the better choice
- Neutral: Decision Analyst -- weighs trade-offs objectively and seeks the best practical outcome

## Rounds
2
```

## Step 4 -- Run agora

Run the following command and wait for it to complete (it may take a minute or two):

```bash
"__AGORA_BIN__" "__DEBATES_DIR__/{guid}/brief.md" --output "__DEBATES_DIR__/{guid}/output"
```

## Step 5 -- Display the synthesis

After agora finishes, find the most recently modified file in `__DEBATES_DIR__/{guid}/output/` and read it. Display the full contents of the report to the user.
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
    scripts_dir = Path(sys.argv[0]).resolve().parent
    agora_bin = scripts_dir / ("agora.exe" if platform.system() == "Windows" else "agora")
    if not agora_bin.exists():
        agora_bin = scripts_dir / "agora"
    if not agora_bin.exists():
        print("Error: could not find agora binary.", file=sys.stderr)
        sys.exit(1)

    python_bin = scripts_dir / ("python.exe" if platform.system() == "Windows" else "python")
    if not python_bin.exists():
        python_bin = scripts_dir / "python"

    agora_bin_posix = agora_bin.as_posix()
    python_bin_posix = python_bin.as_posix()

    workspace = Path.home() / ".agora"
    debates_dir = workspace / "debates"
    debates_dir.mkdir(parents=True, exist_ok=True)

    # Migrate any sessions from the old repo-local debates/ folder
    local_debates = Path(__file__).parent.parent / "debates"
    if local_debates.exists() and local_debates != debates_dir:
        moved = 0
        for session in local_debates.iterdir():
            if session.is_dir():
                dest = debates_dir / session.name
                if not dest.exists():
                    shutil.move(str(session), str(dest))
                    moved += 1
        if moved:
            print(f"Migrated {moved} session(s) from {local_debates} to {debates_dir}")

    debates_posix = debates_dir.as_posix()

    commands_dir = Path.home() / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    content = (
        _DEBATE_COMMAND_TEMPLATE
        .replace("__AGORA_BIN__", agora_bin_posix)
        .replace("__PYTHON_BIN__", python_bin_posix)
        .replace("__DEBATES_DIR__", debates_posix)
    )

    debate_md = commands_dir / "debate.md"
    debate_md.write_text(content, encoding="utf-8")

    print(f"Installed: {debate_md}")
    print(f"Debates:   {debates_dir}")

    _add_to_path(scripts_dir)


def _add_to_path(scripts_dir: Path) -> None:
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
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            rc_file = Path.home() / ".zshrc"
            export_line = f'export PATH="{scripts_dir}:$PATH"'
        elif "fish" in shell:
            rc_file = Path.home() / ".config" / "fish" / "config.fish"
            export_line = f'fish_add_path "{scripts_dir}"'
        else:
            rc_file = Path.home() / ".bashrc"
            export_line = f'export PATH="{scripts_dir}:$PATH"'

        existing = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
        if str(scripts_dir) in existing:
            print(f"PATH already configured in {rc_file}")
        else:
            with open(rc_file, "a", encoding="utf-8") as f:
                f.write(f"\n# Added by agora-setup\n{export_line}\n")
            print(f"Added to PATH in {rc_file}")
            print(f"Run 'source {rc_file}' or open a new terminal for the change to take effect.")


def uninstall():
    """Remove the /debate slash command, workspace, and PATH entry."""
    scripts_dir = Path(sys.argv[0]).resolve().parent

    # Remove /debate slash command
    debate_md = Path.home() / ".claude" / "commands" / "debate.md"
    if debate_md.exists():
        debate_md.unlink()
        print(f"Removed: {debate_md}")
    else:
        print(f"Not found (skipping): {debate_md}")

    # Remove ~/.agora workspace
    workspace = Path.home() / ".agora"
    if workspace.exists():
        import shutil as _shutil
        _shutil.rmtree(workspace)
        print(f"Removed: {workspace}")
    else:
        print(f"Not found (skipping): {workspace}")

    # Remove PATH entry
    _remove_from_path(scripts_dir)

    print("")
    print(f"To finish, delete the repo: {Path(__file__).parent.parent}")


def _remove_from_path(scripts_dir: Path) -> None:
    if platform.system() == "Windows":
        ps_cmd = (
            f'$p = [Environment]::GetEnvironmentVariable("PATH", "User"); '
            f'$p = ($p -split ";" | Where-Object {{ $_ -ne "{scripts_dir}" }}) -join ";"; '
            f'[Environment]::SetEnvironmentVariable("PATH", $p, "User")'
        )
        result = subprocess.run(["powershell", "-Command", ps_cmd])
        if result.returncode == 0:
            print(f"Removed from PATH: {scripts_dir}")
            print("Open a new terminal for the PATH change to take effect.")
        else:
            print(f"Could not update PATH automatically. Remove this manually: {scripts_dir}")
    else:
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            rc_file = Path.home() / ".zshrc"
        elif "fish" in shell:
            rc_file = Path.home() / ".config" / "fish" / "config.fish"
        else:
            rc_file = Path.home() / ".bashrc"

        if rc_file.exists():
            original = rc_file.read_text(encoding="utf-8")
            cleaned = "\n".join(
                line for line in original.splitlines()
                if str(scripts_dir) not in line and line != "# Added by agora-setup"
            )
            rc_file.write_text(cleaned, encoding="utf-8")
            print(f"Removed from PATH in {rc_file}")
            print(f"Run 'source {rc_file}' or open a new terminal for the change to take effect.")


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
        print("pyproject.toml changed -- run 'uv pip install -e .' to pick up new dependencies or entry points.")
    else:
        print("Done.")


def clean():
    """List saved /debate sessions and archive or delete them."""
    workspace = Path.home() / ".agora"
    debates_dir = workspace / "debates"
    archive_dir = workspace / "archive"

    if not debates_dir.exists():
        print("No debates directory found. Nothing to clean.")
        return

    # Collect all session folders with metadata
    sessions = []
    for session_path in sorted(debates_dir.iterdir()):
        if not session_path.is_dir():
            continue

        title = "(untitled)"
        date_str = "unknown date"

        brief_file = session_path / "brief.md"
        if brief_file.exists():
            for line in brief_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("# Brief:"):
                    title = line[len("# Brief:"):].strip()
                    break

        output_dir = session_path / "output"
        if output_dir.exists():
            for f in output_dir.iterdir():
                if f.suffix == ".md":
                    m = re.search(r"(\d{8})-(\d{6})", f.stem)
                    if m:
                        d, t = m.group(1), m.group(2)
                        date_str = f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t[0:2]}:{t[2:4]}:{t[4:6]}"
                    break

        sessions.append((session_path, title, date_str))

    if not sessions:
        print("No debate sessions found.")
        return

    print(f"Found {len(sessions)} debate session(s):\n")
    for i, (_, title, date) in enumerate(sessions, 1):
        print(f"  {i:>2}. [{date}]  {title}")

    print()
    print("Options:")
    print("  [a] Archive all   -- move sessions to ~/.agora/archive/")
    print("  [d] Delete all    -- permanently remove sessions")
    print("  [i] Interactive   -- decide each session individually")
    print("  [q] Quit")
    print()

    choice = input("Choice: ").strip().lower()

    if choice in ("q", ""):
        print("Aborted.")
        return

    def do_archive(path: Path, title: str) -> None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / path.name
        shutil.move(str(path), str(dest))
        print(f"  Archived: {title}")

    def do_delete(path: Path, title: str) -> None:
        shutil.rmtree(path)
        print(f"  Deleted:  {title}")

    if choice == "a":
        print(f"\nArchiving {len(sessions)} session(s)...")
        for path, title, _ in sessions:
            do_archive(path, title)
        print(f"\nDone. Archived to: {archive_dir}")

    elif choice == "d":
        confirm = input(f"\nPermanently delete all {len(sessions)} session(s)? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
        for path, title, _ in sessions:
            do_delete(path, title)
        print("\nDone.")

    elif choice == "i":
        print()
        archived = deleted = skipped = 0
        for path, title, date in sessions:
            print(f"  [{date}]  {title}")
            action = input("    [a] Archive  [d] Delete  [s] Skip -- action: ").strip().lower()
            if action == "a":
                do_archive(path, title)
                archived += 1
            elif action == "d":
                do_delete(path, title)
                deleted += 1
            else:
                print("    Skipped.")
                skipped += 1
            print()
        print(f"Done. Archived: {archived}  Deleted: {deleted}  Skipped: {skipped}")

    else:
        print("Invalid choice. Aborted.")


def help_cmd():
    """Show help for all agora-* commands."""
    print("""
Agora -- autonomous multi-agent debate tool
==========================================

Commands:

  agora <brief.md> [options]
      Run a structured multi-agent debate from a markdown brief file.
      Reports are written to the output directory on completion.

      Options:
        --rounds N       Number of debate rounds (default: from brief, or 2)
        --output DIR     Directory to write the report (default: ./output)
        --model MODEL    Claude model to use (e.g. claude-opus-4-6)

      Env var:  AGORA_MODEL=<model>  -- set a default model without --model

  agora-setup
      Install the /debate Claude Code slash command and add agora to your PATH.
      Run once after cloning and installing the package.

  agora-update
      Pull the latest changes from git.
      Tells you if a reinstall (uv pip install -e .) is needed.

  agora-clean
      List all /debate sessions stored in ~/.agora/debates/ and choose to:
        - Archive them  -> moved to ~/.agora/archive/
        - Delete them   -> permanently removed
        - Interactive   -> decide each session one at a time

  agora-uninstall
      Remove the /debate slash command, the ~/.agora/ workspace directory,
      and the PATH entry added by agora-setup.
      Delete the repo folder afterwards to complete removal.

  agora-help
      Show this message.

Quick start:
  /debate REST vs GraphQL     run a debate inside any Claude Code conversation
  agora briefs/example.md     run a debate from a brief file on the command line

Writing a brief:
  Only ## Topic and ## Context are required. Add ## Personas, ## Constraints,
  and ## Rounds to customise the debate. See briefs/example_orm.md for a
  full example.
""")

