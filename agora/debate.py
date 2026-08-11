import asyncio
from .models import Brief, Persona, AgentTurn, DebateTranscript

POSITION_LABELS = {
    "for": "arguing IN FAVOUR",
    "against": "arguing AGAINST",
    "neutral": "acting as a neutral mediator",
}


def _build_prompt(
    persona: Persona,
    brief: Brief,
    previous_turns: list[AgentTurn],
    task: str,
) -> str:
    position_label = POSITION_LABELS.get(persona.position, "participating")

    constraints_block = ""
    if brief.constraints:
        lines = "\n".join(f"- {c}" for c in brief.constraints)
        constraints_block = f"\n\nConstraints the debate must respect:\n{lines}"

    history_block = ""
    if previous_turns:
        sections = {}
        for t in previous_turns:
            sections.setdefault(t.round_number, []).append(t)

        parts = []
        for rnum in sorted(sections):
            heading = "Opening Statements" if rnum == 1 else f"Round {rnum} — Rebuttals"
            parts.append(f"### {heading}")
            for t in sections[rnum]:
                parts.append(f"\n**{t.persona.role} ({t.persona.position}):**\n{t.content}")
        history_block = "\n\n## Debate So Far\n\n" + "\n\n".join(parts)

    return f"""You are {persona.role}, {position_label} in a structured debate.

## Debate Topic
{brief.topic}

## Background Context
{brief.context}{constraints_block}

## Your Role
{persona.focus or position_label.capitalize()}

## Instructions
- Be direct and substantive. Make concrete arguments grounded in the context above.
- Do NOT capitulate simply because another agent pushes back — hold your position unless genuinely persuaded.
- Keep your response to 3–4 focused paragraphs.
- Lead immediately with your argument. No greetings or filler phrases.
{history_block}

## Your Task
{task}"""


async def _call_claude(prompt: str, model: str | None) -> str:
    cmd = ["claude", "-p", prompt]
    if model:
        cmd += ["--model", model]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(f"claude CLI error (exit {proc.returncode}): {err}")

    return stdout.decode().strip()


async def _run_round(
    model: str | None,
    brief: Brief,
    personas: list[Persona],
    all_turns: list[AgentTurn],
    round_number: int,
) -> list[AgentTurn]:
    async def run_one(persona: Persona) -> AgentTurn:
        previous = [t for t in all_turns if t.persona.name != persona.name]

        if round_number == 1:
            task = (
                f"Present your opening statement on: {brief.topic}\n\n"
                "Make your strongest case. Be specific to the context provided."
            )
        else:
            others_this_round = [
                t for t in all_turns
                if t.round_number == round_number - 1 and t.persona.name != persona.name
            ]
            others_text = "\n\n".join(
                f"{t.persona.role} ({t.persona.position}):\n{t.content}"
                for t in others_this_round
            )
            task = (
                f"Round {round_number} rebuttal.\n\n"
                f"Here is what the other participants said last round:\n\n{others_text}\n\n"
                "Challenge the weakest points in their arguments directly. "
                "Acknowledge valid points briefly, then press your own case harder."
            )

        prompt = _build_prompt(persona, brief, previous, task)
        content = await _call_claude(prompt, model)
        return AgentTurn(persona=persona, round_number=round_number, content=content)

    return list(await asyncio.gather(*[run_one(p) for p in personas]))


async def _run_synthesis(model: str | None, brief: Brief, transcript: list[AgentTurn]) -> str:
    transcript_text = ""
    current_round = 0
    for turn in transcript:
        if turn.round_number != current_round:
            current_round = turn.round_number
            label = "Opening Statements" if current_round == 1 else f"Round {current_round} — Rebuttals"
            transcript_text += f"\n\n### {label}\n"
        transcript_text += f"\n**{turn.persona.role} ({turn.persona.position}):**\n{turn.content}\n"

    constraints_block = ""
    if brief.constraints:
        lines = "\n".join(f"- {c}" for c in brief.constraints)
        constraints_block = f"\n\nConstraints:\n{lines}"

    prompt = f"""You are a neutral senior decision-maker synthesising a structured debate.

TOPIC: {brief.topic}

CONTEXT: {brief.context}{constraints_block}

FULL DEBATE TRANSCRIPT:
{transcript_text}

Produce a structured synthesis with these exact sections:

## Summary
A 2–3 sentence executive summary of the debate outcome.

## Decision Matrix
A markdown table with columns: Factor | Weight (High/Med/Low) | Favours | Notes
Include 4–7 of the most decision-relevant factors raised in the debate.

## Key Disagreements
Bullet list of the genuine unresolved disagreements.

## Areas of Agreement
Bullet list of points where all sides converged.

## Recommendation
A clear recommendation with 2–3 sentences of reasoning. If the answer is genuinely context-dependent, state the deciding condition explicitly."""

    return await _call_claude(prompt, model)


async def run_debate(
    brief: Brief,
    model: str | None,
    progress_callback=None,
) -> DebateTranscript:
    all_turns: list[AgentTurn] = []

    for round_num in range(1, brief.rounds + 1):
        if progress_callback:
            label = "Opening statements" if round_num == 1 else f"Round {round_num} rebuttals"
            progress_callback(f"[Round {round_num}/{brief.rounds}] {label}...")

        turns = await _run_round(model, brief, brief.personas, all_turns, round_num)
        all_turns.extend(turns)

    if progress_callback:
        progress_callback("Synthesising debate...")

    synthesis = await _run_synthesis(model, brief, all_turns)
    return DebateTranscript(brief=brief, turns=all_turns, synthesis=synthesis)
