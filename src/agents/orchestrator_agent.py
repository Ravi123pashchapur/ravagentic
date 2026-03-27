from typing import Any, Dict

from .types import AgentResult, GlobalContext
from .tool_registry import TOOL_REGISTRY
from .llm_client import call_llm_text


class FlowControllerSubAgent:
    def next_state(self, state: str) -> str:
        return state


class ToolRouterSubAgent:
    def route(self, context: GlobalContext) -> Dict[str, Any]:
        """
        Tool routing must remain deterministic/validated.
        LLM is used only to generate a short rationale.
        """
        allowed = list(TOOL_REGISTRY.keys())
        routing: Dict[str, Any] = {"mode": "langchain-tools", "tool_names": allowed}

        # Best-effort LLM rationale (no functional impact).
        try:
            openai_api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
            if openai_api_key:
                note = call_llm_text(
                    context,
                    role_name="ToolRouterSubAgent",
                    system_prompt="Write a short rationale for selecting these tools for the workflow.",
                    user_prompt=f"Allowed tools: {allowed}. Return 1 short sentence.",
                )
                routing["routing_note"] = note
        except Exception:
            routing["routing_note"] = ""

        return routing


class ContextManagerSubAgent:
    def merge(self, context: GlobalContext, artifact_key: str, artifact_value: object) -> None:
        context.artifacts[artifact_key] = artifact_value
        # Best-effort LLM validation note.
        try:
            openai_api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
            if openai_api_key:
                note = call_llm_text(
                    context,
                    role_name="ContextManagerSubAgent",
                    system_prompt="Write a short note confirming the artifact looks well-formed for the workflow.",
                    user_prompt=f"artifact_key={artifact_key}\nartifact_value_preview={str(artifact_value)[:500]}",
                )
                context.artifacts[f"{artifact_key}__note"] = note
        except Exception:
            # Never fail workflow due to optional notes.
            pass


class RecoverySubAgent:
    def recommend(self, failed_gate: str) -> str:
        return f"Retry phase for gate: {failed_gate}"

    def recommend_with_llm(self, context: GlobalContext, failed_gate: str) -> str:
        try:
            openai_api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
            if not openai_api_key:
                return self.recommend(failed_gate)
            return call_llm_text(
                context,
                role_name="RecoverySubAgent",
                system_prompt="Write a short human-readable recovery recommendation.",
                user_prompt=f"failed_gate={failed_gate}\nDescribe what to retry next in 1 sentence.",
            )
        except Exception:
            return self.recommend(failed_gate)


class PromptRefinerSubAgent:
    def run(self, context: GlobalContext) -> Dict[str, str]:
        raw_prompt = str(context.user_theme_input.get("ui_prompt", "")).strip()
        theme_name = str(context.user_theme_input.get("theme_name", "modern-dark")).strip()
        style_keywords = context.user_theme_input.get("style_keywords", [])
        reference_template_path = str(
            context.requirements.get("reference_template_path", "")
        ).strip()
        openai_api_key = str(context.requirements.get("openai_api_key", "")).strip()
        openai_model = str(context.requirements.get("openai_model", "gpt-5.1")).strip()
        llm_connected = bool(openai_api_key)

        fallback_refined = (
            f"Design a {theme_name} Next.js UI. "
            f"Intent: {raw_prompt or 'Create a polished themed dashboard experience.'} "
            f"Style keywords: {', '.join(style_keywords) if style_keywords else 'minimal, responsive'}. "
            "Must connect each core route to backend contracts and avoid image generation."
        )
        if reference_template_path:
            fallback_refined += (
                f" Use reference template at '{reference_template_path}' as inspiration only; "
                "do not copy code or assets."
            )
        if not openai_api_key:
            return {
                "raw_prompt": raw_prompt,
                "refined_prompt": fallback_refined,
                "refinement_mode": "local_fallback_no_api_key",
                "llm_connected": llm_connected,
            }
        try:
            # Use the shared LLM wrapper to avoid duplicated raw HTTP code.
            refined = call_llm_text(
                context,
                role_name="PromptRefinerSubAgent",
                system_prompt=(
                    "You refine UI implementation prompts for agentic orchestration. "
                    "Return only the final refined prompt text."
                ),
                user_prompt=(
                    f"Theme: {theme_name}\n"
                    f"Raw user intent: {raw_prompt or 'Create a polished themed dashboard experience.'}\n"
                    f"Style keywords: {', '.join(style_keywords) if style_keywords else 'minimal, responsive'}\n"
                    f"Reference template path: {reference_template_path or 'not provided'}\n"
                    "Constraints: Next.js frontend, must connect routes to backend contracts, no image generation, "
                    "inspiration-only reference usage (no direct copy)."
                ),
            )
            return {
                "raw_prompt": raw_prompt,
                "refined_prompt": refined,
                "refinement_mode": f"openai:{openai_model}",
                "llm_connected": llm_connected,
            }
        except Exception:
            return {
                "raw_prompt": raw_prompt,
                "refined_prompt": fallback_refined,
                "refinement_mode": "local_fallback_openai_error",
                "llm_connected": llm_connected,
            }


class OrchestratorAgent:
    def __init__(self) -> None:
        self.flow = FlowControllerSubAgent()
        self.router = ToolRouterSubAgent()
        self.context_mgr = ContextManagerSubAgent()
        self.recovery = RecoverySubAgent()
        self.prompt_refiner = PromptRefinerSubAgent()

    def refine_prompt(self, context: GlobalContext) -> AgentResult:
        payload = self.prompt_refiner.run(context)
        llm_connected = bool(payload.get("llm_connected", False))
        return AgentResult(
            status="success",
            agent="O",
            summary="Prompt refinement stage completed.",
            findings=[
                {
                    "id": "O-PR-001",
                    "severity": "low",
                    "message": "Refined UI prompt generated for downstream agents.",
                    "action": "Continue with orchestrator context initialization.",
                }
            ],
            artifacts={
                "prompt_refinement": payload,
                "llm_connectivity": {
                    "PromptRefinerSubAgent": llm_connected,
                },
            },
            next_recommendation="Invoke orchestrator context init.",
            context_version_out=context.context_version,
        )

    def init_context(self, context: GlobalContext) -> AgentResult:
        routing = self.router.route(context)
        tool_names = routing.get("tool_names", [])
        context.memory.setdefault("tool_names", [])
        context.memory["tool_names"] = tool_names
        self.context_mgr.merge(context, "tool_registry", tool_names)
        if routing.get("routing_note"):
            self.context_mgr.merge(context, "tool_registry__routing_note", routing.get("routing_note"))

        # Best-effort recovery note from LLM (no functional impact).
        recovery_note = ""
        try:
            recovery_note = self.recovery.recommend_with_llm(context, "workflow_start")
        except Exception:
            recovery_note = ""

        # Cleaner: attach a human-readable “flow” note from the LLM (best-effort).
        flow_note = ""
        try:
            openai_api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
            if openai_api_key:
                flow_note = call_llm_text(
                    context,
                    role_name="FlowControllerSubAgent",
                    system_prompt="Write a single short sentence describing the next workflow stage.",
                    user_prompt="Next stage after context init is planner phase (P). Keep it concise.",
                )
        except Exception:
            flow_note = ""

        openai_api_key = str(context.requirements.get("openai_api_key", "") or "").strip()
        llm_connected = bool(openai_api_key)

        return AgentResult(
            status="success",
            agent="O",
            summary="Context initialized and orchestration started.",
            artifacts={
                "context_version": context.context_version,
                "tool_registry": tool_names,
                "flow_controller_note": flow_note,
                "recovery_note": recovery_note,
                "llm_connectivity": {
                    "FlowControllerSubAgent": False,
                    "ToolRouterSubAgent": llm_connected,
                    "ContextManagerSubAgent": llm_connected,
                    "RecoverySubAgent": llm_connected,
                },
            },
            next_recommendation="Invoke planner phase.",
            context_version_out=context.context_version,
        )
