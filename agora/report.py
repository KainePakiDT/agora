from datetime import datetime
from pathlib import Path
import re
from .models import DebateTranscript


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:60]


def render(transcript: DebateTranscript, model: str, output_dir: Path) -> Path:
    brief = transcript.brief
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    slug = _slugify(brief.title)
    filename = f"{slug}-{timestamp}.md"
    output_path = output_dir / filename

    lines = [
        f"# Debate Report: {brief.title}",
        f"",
        f"**Date:** {now.strftime('%Y-%m-%d %H:%M')}  "
        f"**Model:** `{model}`  "
        f"**Rounds:** {brief.rounds}  "
        f"**Participants:** {', '.join(p.role for p in brief.personas)}",
        f"",
        f"---",
        f"",
        f"## Topic",
        f"",
        brief.topic,
        f"",
    ]

    if brief.context:
        lines += [
            f"## Context",
            f"",
            brief.context,
            f"",
        ]

    if brief.constraints:
        lines += [f"## Constraints", f""]
        for c in brief.constraints:
            lines.append(f"- {c}")
        lines.append("")

    # Transcript grouped by round
    current_round = 0
    for turn in transcript.turns:
        if turn.round_number != current_round:
            current_round = turn.round_number
            heading = "Opening Statements" if current_round == 1 else f"Round {current_round} — Rebuttals"
            lines += [f"---", f"", f"## {heading}", f""]

        position_tag = f"*{turn.persona.position}*"
        lines += [
            f"### {turn.persona.role} ({position_tag})",
            f"",
            turn.content,
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## Synthesis",
        f"",
        transcript.synthesis,
        f"",
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
