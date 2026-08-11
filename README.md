# Agora

Autonomous multi-agent debate tool powered by Claude. Drop a markdown brief, step away, and get a structured report with a decision matrix and recommendation.

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/agora.git
cd agora
uv venv && uv pip install -e .

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Run a debate
.venv/Scripts/agora briefs/example_orm.md
```

Reports are written to `output/`.

## Brief format

Create a markdown file following this schema:

```markdown
# Brief: Your Decision Title

## Topic
The specific question to debate.

## Context
Background the agents need — team size, tech stack, constraints, history.

## Constraints (optional)
- Hard limits the debate must respect
- e.g. no full rewrites, budget cap, deadline

## Personas (optional)
- For: Role Name — what they focus on
- Against: Role Name — what they focus on
- Neutral: Role Name — what they focus on

## Rounds (optional)
2
```

If `## Personas` is omitted, three defaults are used: **Advocate**, **Skeptic**, and **Pragmatist**.

## CLI options

```
agora <brief.md> [--rounds N] [--output DIR] [--model MODEL]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--rounds` | from brief or `2` | Number of debate rounds |
| `--output` | `output/` | Directory to write the report |
| `--model` | `claude-opus-4-6` | Claude model to use |

Override the model via env var: `AGORA_MODEL=claude-sonnet-4-6`.

## How it works

1. Brief is parsed into topic, context, constraints, and personas
2. **Round 1** — all agents write opening statements in parallel (no knowledge of each other)
3. **Round 2..N** — all agents write rebuttals in parallel (each receives the previous round's other statements)
4. **Synthesis** — a separate call produces a decision matrix, key disagreements, areas of agreement, and a recommendation
5. Report saved to `output/{title}-{timestamp}.md`
