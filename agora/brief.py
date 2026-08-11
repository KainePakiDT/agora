import re
from pathlib import Path
from .models import Brief, Persona

DEFAULT_PERSONAS = [
    Persona(name="Advocate", role="Advocate", position="for", focus="argues strongly in favour of the proposal"),
    Persona(name="Skeptic", role="Skeptic", position="against", focus="argues strongly against the proposal"),
    Persona(name="Pragmatist", role="Pragmatist", position="neutral", focus="seeks practical trade-offs and consensus"),
]

POSITION_KEYWORDS = {
    "for": "for",
    "pro": "for",
    "in favour": "for",
    "in favor": "for",
    "against": "against",
    "con": "against",
    "anti": "against",
    "neutral": "neutral",
    "mediator": "neutral",
    "balanced": "neutral",
}


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_personas(raw: str) -> list[Persona]:
    personas = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue

        # Format: "Position: Role — focus" or "Position: Role - focus"
        position = "neutral"
        for keyword, pos in POSITION_KEYWORDS.items():
            if line.lower().startswith(keyword + ":"):
                position = pos
                line = line[len(keyword) + 1:].strip()
                break

        # Split on em-dash or regular dash for focus description
        parts = re.split(r"\s*[—–-]\s*", line, maxsplit=1)
        role = parts[0].strip()
        focus = parts[1].strip() if len(parts) > 1 else ""

        personas.append(Persona(name=role, role=role, position=position, focus=focus))

    return personas if personas else DEFAULT_PERSONAS


def parse_brief(path: Path) -> Brief:
    text = path.read_text(encoding="utf-8")

    # Title from the first # heading
    title_match = re.search(r"^#\s+(?:Brief:\s*)?(.+)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    topic = _extract_section(text, "Topic")
    context = _extract_section(text, "Context")

    constraints_raw = _extract_section(text, "Constraints")
    constraints = [
        line.strip().lstrip("-").strip()
        for line in constraints_raw.splitlines()
        if line.strip().lstrip("-").strip()
    ]

    personas_raw = _extract_section(text, "Personas")
    personas = _parse_personas(personas_raw) if personas_raw else list(DEFAULT_PERSONAS)

    rounds_raw = _extract_section(text, "Rounds")
    try:
        rounds = int(rounds_raw.strip())
    except (ValueError, AttributeError):
        rounds = 2

    return Brief(
        title=title,
        topic=topic,
        context=context,
        constraints=constraints,
        personas=personas,
        rounds=rounds,
    )
