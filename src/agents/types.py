from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentResult:
    status: str
    agent: str
    summary: str
    findings: List[Dict[str, str]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    next_recommendation: str = ""
    context_version_out: str = "v1"


@dataclass
class GlobalContext:
    session_id: str
    project: str
    user_theme_input: Dict[str, Any]
    requirements: Dict[str, Any]
    constraints: Dict[str, Any]
    acceptance_criteria: List[str]
    artifacts: Dict[str, Any] = field(default_factory=dict)
    quality_gates: Dict[str, str] = field(default_factory=dict)
    # Simple shared memory across agents/sub-agents for LLM prompt context.
    memory: Dict[str, Any] = field(default_factory=dict)
    context_version: str = "v1"
