from pathlib import Path
from typing import Any, Dict


def repo_root() -> Path:
    # src/agents/tool_registry.py -> src/agents -> src -> repo root
    return Path(__file__).resolve().parents[2]


def read_repo_text(relative_path: str, *, max_chars: int = 60000) -> str:
    """
    Safe-ish helper for LLM/tool prompts.
    - relative_path must be inside the repo root.
    - caps output size to avoid flooding.
    """
    base = repo_root()
    p = (base / relative_path).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError("Path escapes repo root.")
    text = p.read_text(encoding="utf-8")
    return text[:max_chars]


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "read_repo_text": {
        "description": "Read a text file relative to repo root (capped output).",
        "call_signature": "read_repo_text(relative_path: str, max_chars: int = 60000) -> str",
    },
}

