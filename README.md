# Agora

Autonomous multi-agent debate tool that runs on top of the **Claude Code CLI**. Drop a markdown brief, step away, and get a structured report with a decision matrix and recommendation.

No API key needed — uses your existing Claude Code subscription.

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and authenticated (`claude` must be on your PATH)

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/KainePakiDT/agora.git
cd agora
uv venv && uv pip install -e .

# 2. Run a debate
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
| `--model` | claude CLI default | Pass a specific model to the claude CLI |

Override the model via env var: `AGORA_MODEL=claude-sonnet-4-6`.

## How it works

1. Brief is parsed into topic, context, constraints, and personas
2. **Round 1** — all agents write opening statements in parallel via `claude -p`
3. **Round 2..N** — all agents write rebuttals in parallel (each receives the previous round's other statements)
4. **Synthesis** — a separate call produces a decision matrix, key disagreements, areas of agreement, and a recommendation
5. Report saved to `output/{title}-{timestamp}.md`
