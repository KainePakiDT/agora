import asyncio
from anthropic import AsyncAnthropic
from .models import Brief, Persona, AgentTurn, DebateTranscript

POSITION_LABELS = {
    "for": "arguing IN FAVOUR",
    "against": "arguing AGAINST",
    "neutral": "acting as a neutral mediator",
}


def _build_system_prompt(persona: Persona, brief: Brief) -> str:
    position_label = POSITION_LABELS.get(persona.position, "participating")
    constraints_block = ""
    if brief.constraints:
        lines = "\n".join(f"- {c}" for c in brief.constraints)
        constraints_block = f"\n\nConstraints the debate must respect:\n{lines}"

    return f"""You are {persona.role}, {position_label} in a structured debate.

DEBATE TOPIC: {brief.topic}

BACKGROUND CONTEXT:
{brief.context}{constraints_block}

YOUR ROLE: {persona.focus or position_label.capitalize()}

Instructions:
- Be direct and substantive. Make concrete arguments, not vague generalisations.
- Cite specific risks, costs, or benefits relevant to the context provided.
- Do NOT capitulate simply because another agent pushes back — hold your position unless genuinely persuaded.
- Keep responses to 3–4 focused paragraphs.
- Do not greet or use filler phrases. Lead with your argument."""


def _build_opening_prompt(brief: Brief) -> str:
    return (
        f"Present your opening statement on the following question:\n\n{brief.topic}\n\n"
        "Make your strongest case. Be specific to the context provided."
    )


def _build_rebuttal_prompt(other_turns: list[AgentTurn], round_number: int) -> str:
    others = "\n\n".join(
        f"--- {t.persona.role} ({t.persona.position}) ---\n{t.content}"
        for t in other_turns
    )
    return (
        f"Round {round_number}. Here is what the other participants said in the previous round:\n\n"
        f"{others}\n\n"
        "Now provide your rebuttal. Challenge the weakest points in their arguments directly. "
        "Acknowledge any valid points briefly, then press your own case harder."
    )


async def _call_agent(
    client: AsyncAnthropic,
    model: str,
    persona: Persona,
    brief: Brief,
    history: list[dict],
    prompt: str,
) -> str:
    messages = history + [{"role": "user", "content": prompt}]
    response = await client.messages.create(
        model=model,
        max_tokens=1200,
        system=_build_system_prompt(persona, brief),
        messages=messages,
    )
    return response.content[0].text


async def _run_round(
    client: AsyncAnthropic,
    model: str,
    brief: Brief,
    personas: list[Persona],
    histories: dict[str, list[dict]],
    round_number: int,
    previous_turns: list[AgentTurn],
) -> list[AgentTurn]:
    if round_number == 1:
        prompt_fn = lambda p: _build_opening_prompt(brief)
    else:
        def prompt_fn(p: Persona) -> str:
            others = [t for t in previous_turns if t.persona.name != p.name]
            return _build_rebuttal_prompt(others, round_number)

    tasks = {
        p.name: _call_agent(
            client, model, p, brief, histories[p.name], prompt_fn(p)
        )
        for p in personas
    }

    results = await asyncio.gather(*tasks.values())
    name_list = list(tasks.keys())

    turns = []
    for name, content in zip(name_list, results):
        persona = next(p for p in personas if p.name == name)
        turn = AgentTurn(persona=persona, round_number=round_number, content=content)
        turns.append(turn)

        prompt_used = prompt_fn(persona)
        histories[name].append({"role": "user", "content": prompt_used})
        histories[name].append({"role": "assistant", "content": content})

    return turns


async def _run_synthesis(
    client: AsyncAnthropic,
    model: str,
    brief: Brief,
    transcript: list[AgentTurn],
) -> str:
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

    response = await client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def run_debate(brief: Brief, model: str, progress_callback=None) -> DebateTranscript:
    client = AsyncAnthropic()
    personas = brief.personas
    histories: dict[str, list[dict]] = {p.name: [] for p in personas}
    all_turns: list[AgentTurn] = []

    for round_num in range(1, brief.rounds + 1):
        if progress_callback:
            label = "Opening statements" if round_num == 1 else f"Round {round_num} rebuttals"
            progress_callback(f"[Round {round_num}/{brief.rounds}] {label}...")

        previous = [t for t in all_turns if t.round_number == round_num - 1]
        turns = await _run_round(client, model, brief, personas, histories, round_num, previous)
        all_turns.extend(turns)

    if progress_callback:
        progress_callback("Synthesising debate...")

    synthesis = await _run_synthesis(client, model, brief, all_turns)

    return DebateTranscript(brief=brief, turns=all_turns, synthesis=synthesis)
