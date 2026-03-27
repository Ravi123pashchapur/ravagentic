import json
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .types import GlobalContext


def _palette_from_context(context: GlobalContext) -> List[str]:
    palette = context.user_theme_input.get("palette") or ["#0b1020", "#6366f1", "#f9fafb"]
    if isinstance(palette, list):
        return [str(x) for x in palette]
    return [str(palette)]


def _fallback_json(context: GlobalContext, role_name: str) -> Any:
    """
    Deterministic fallback outputs so the pipeline keeps running.
    This is critical for reliability when OPENAI is missing/unreachable.
    """
    theme_name = str(context.user_theme_input.get("theme_name", "modern-dark"))
    acceptance_criteria = list(context.acceptance_criteria or [])
    palette = _palette_from_context(context)

    expected_api_map = {
        "/": "GET /api/home",
        "/dashboard": "GET /api/dashboard",
        "/settings": "GET /api/settings",
        "/profile": "GET /api/profile",
    }
    expected_folders = ["frontend/src/app", "frontend/src/lib/api", "backend/src/routes"]
    default_tasks = [
        "Create route contracts",
        "Prepare frontend component plan",
        "Prepare backend integration checkpoints",
    ]
    if role_name == "RequirementParserSubAgent":
        return {"theme": theme_name}
    if role_name == "TaskDecomposerSubAgent":
        return {"tasks": default_tasks}
    if role_name == "AcceptanceCriteriaSubAgent":
        return {"acceptance_criteria": acceptance_criteria[:3]}
    if role_name == "RiskEstimatorSubAgent":
        return {"risks": ["Contract drift", "Route mismatch", "Schema mismatch"]}
    if role_name == "TemplateScoutSubAgent":
        return {"templates": ["dashboard", "profile", "settings", "landing"]}
    if role_name == "DesignSystemSubAgent":
        primary = palette[0] if len(palette) > 0 else "#0b1020"
        accent = palette[1] if len(palette) > 1 else "#6366f1"
        text = palette[2] if len(palette) > 2 else "#f9fafb"
        return {"tokens": {"primary": primary, "accent": accent, "text": text}}
    if role_name == "IntegrationBlueprintSubAgent":
        return {"api_map": expected_api_map}
    if role_name == "FolderStrategySubAgent":
        return {"folders": expected_folders}

    # Generic empty fallback.
    return {}


def _get_llm(context: GlobalContext) -> ChatOpenAI:
    api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
    model = str(context.requirements.get("openai_model", "gpt-5.1") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in requirements/context.")
    return ChatOpenAI(model=model, api_key=api_key, temperature=0.2)


def call_llm_text(
    context: GlobalContext,
    *,
    role_name: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    try:
        llm = _get_llm(context)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"[role={role_name}]\n{user_prompt}"),
        ]
        resp = llm.invoke(messages)
        return str(resp.content or "").strip()
    except Exception:
        # Keep it short and deterministic.
        return f"[LLM_FALLBACK:{role_name}] {user_prompt[:80]}".strip()


def call_llm_json(
    context: GlobalContext,
    *,
    role_name: str,
    system_prompt: str,
    user_prompt: str,
) -> Any:
    """
    Expects the LLM to return *only* a valid JSON payload in resp.content.
    """
    try:
        llm = _get_llm(context)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"[role={role_name}]\n"
                    f"{user_prompt}\n\n"
                    "Return ONLY valid JSON. No markdown, no extra keys, no explanations."
                )
            ),
        ]
        resp = llm.invoke(messages)
        content = str(resp.content or "").strip()
        return json.loads(content)
    except Exception:
        return _fallback_json(context, role_name)

