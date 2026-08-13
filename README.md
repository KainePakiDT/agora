# Agora

Autonomous multi-agent debate tool that runs on top of the **Claude Code CLI**. Drop a markdown brief, step away, and get a structured report with a decision matrix and recommendation.

No API key needed — uses your existing Claude Code subscription.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and signed in
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)

Verify both are available:

```bash
claude --version
uv --version
```

---

## Setup (one time)

```bash
git clone https://github.com/KainePakiDT/agora.git
cd agora
```

Then run the install script for your platform:

```bash
# Mac / Linux
bash install.sh

# Windows
install.bat
```

This will:
- Create a virtual environment and install agora
- Install the `/debate` Claude Code slash command to `~/.claude/commands/`
- Create a `~/.agora/` workspace for briefs and output
- Add agora to your PATH permanently

Open a new terminal after setup — `agora`, `agora-setup`, and `agora-update` will then work from anywhere.

## Updating

```bash
agora-update
```

Pulls the latest changes from the git repo. If `pyproject.toml` changed (new dependencies or entry points), you will be prompted to reinstall manually.

## Uninstalling

From the repo directory:

```bash
# Mac / Linux
bash uninstall.sh

# Windows
uninstall.bat
```

This removes the `/debate` slash command, the `~/.agora/` workspace, and the PATH entry. Then delete the repo folder to finish.

Alternatively, if agora is already on your PATH:

```bash
agora-uninstall
```

---

## Running a debate

```bash
agora briefs/your-brief.md
```

The debate runs automatically. When it finishes, the report is written to `~/.agora/output/`.

### Try the included example

```bash
agora briefs/example_orm.md
```

---

## Writing a brief

Create a `.md` file in `briefs/`. Only **Topic** and **Context** are required — everything else has sensible defaults.

```markdown
# Brief: Your Decision Title

## Topic
The specific question to debate.

## Context
Background the agents need to reason well — team size, tech stack,
existing patterns, relevant history. More detail = better debate.

## Constraints (optional)
- Hard limits the debate must respect
- e.g. no full rewrites, must support unit testing, budget cap

## Personas (optional)
- For: Role Name — what they focus on
- Against: Role Name — what they focus on
- Neutral: Role Name — what they focus on

## Rounds (optional)
2
```

**Persona positions** are detected by keywords at the start of each line:
`For` / `Pro` → arguing in favour
`Against` / `Con` → arguing against
`Neutral` / `Mediator` → seeking consensus

If `## Personas` is omitted entirely, three defaults are used: **Advocate**, **Skeptic**, and **Pragmatist**.

---

## CLI options

```
agora <brief.md> [--rounds N] [--output DIR] [--model MODEL]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--rounds` | from brief, or `2` | Number of debate rounds |
| `--output` | `output/` | Directory to write the report |
| `--model` | claude CLI default | Model to use (e.g. `claude-opus-4-6`) |

You can also set the model via environment variable:

```bash
AGORA_MODEL=claude-sonnet-4-6 agora briefs/my-brief.md
```

---

## Output

Reports are saved to `output/<title>-<timestamp>.md` and contain:

- Full debate transcript grouped by round
- **Summary** — 2–3 sentence executive summary
- **Decision Matrix** — key factors, weights, and which side each favours
- **Key Disagreements** — unresolved splits
- **Areas of Agreement** — where all agents converged
- **Recommendation** — a clear call with reasoning

---

## How it works

1. The brief is parsed into topic, context, constraints, and personas
2. **Round 1** — all agents write opening statements in parallel (no knowledge of each other)
3. **Round 2..N** — all agents write rebuttals in parallel (each sees the previous round's other statements)
4. **Synthesis** — a separate agent call produces the decision matrix and recommendation
5. The full transcript and synthesis are rendered into a markdown report
