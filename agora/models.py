from dataclasses import dataclass, field


@dataclass
class Persona:
    name: str
    role: str
    position: str  # "for", "against", or "neutral"
    focus: str = ""  # optional description of what they focus on


@dataclass
class Brief:
    title: str
    topic: str
    context: str
    constraints: list[str] = field(default_factory=list)
    personas: list[Persona] = field(default_factory=list)
    rounds: int = 2


@dataclass
class AgentTurn:
    persona: Persona
    round_number: int
    content: str


@dataclass
class DebateTranscript:
    brief: Brief
    turns: list[AgentTurn] = field(default_factory=list)
    synthesis: str = ""
