from .llm_client import call_llm_json, call_llm_text
from .types import AgentResult, GlobalContext


class RequirementParserSubAgent:
    def run(self, context: GlobalContext) -> dict:
        theme_name = str(context.user_theme_input.get("theme_name", "modern-dark"))
        ui_prompt = str(context.user_theme_input.get("ui_prompt", "") or "")
        system = "You extract minimal structured requirements for a UI generation workflow."
        user = (
            f"theme_name: {theme_name}\n"
            f"ui_prompt: {ui_prompt}\n\n"
            "Return JSON with exactly: {\"theme\": <theme_name>}"
        )
        return call_llm_json(
            context,
            role_name="RequirementParserSubAgent",
            system_prompt=system,
            user_prompt=user,
        )


class TaskDecomposerSubAgent:
    def run(self, context: GlobalContext) -> list:
        system = "You create a short task backlog for an agentic workflow."
        user = (
            "Create 3-6 tasks for building a themed Next.js UI connected to a mock backend.\n"
            "Return JSON with key \"tasks\" as an array of strings.\n"
            f"Theme: {context.user_theme_input.get('theme_name')}\n"
            f"Constraints: no image generation, connect core routes to backend contracts.\n"
        )
        payload = call_llm_json(
            context,
            role_name="TaskDecomposerSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        return payload.get("tasks", [])


class AcceptanceCriteriaSubAgent:
    def run(self, context: GlobalContext) -> list:
        system = "You convert requirements into measurable acceptance criteria."
        user = (
            "Using the provided acceptance criteria goals, return JSON with key \"acceptance_criteria\" "
            "as an array of 3 strings.\n"
            f"Goals: {context.acceptance_criteria}\n"
        )
        payload = call_llm_json(
            context,
            role_name="AcceptanceCriteriaSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        return payload.get("acceptance_criteria", context.acceptance_criteria)


class RiskEstimatorSubAgent:
    def run(self, context: GlobalContext) -> list:
        system = "You estimate likely risks for implementing a themed UI connected to a mock backend."
        user = (
            "Return JSON with key \"risks\" as an array of 3 strings.\n"
            f"Theme: {context.user_theme_input.get('theme_name')}\n"
            "Consider contract drift, route mismatch, schema mismatch."
        )
        payload = call_llm_json(
            context,
            role_name="RiskEstimatorSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        return payload.get("risks", [])


class PlannerAgent:
    def __init__(self) -> None:
        self.requirement = RequirementParserSubAgent()
        self.decomposer = TaskDecomposerSubAgent()
        self.criteria = AcceptanceCriteriaSubAgent()
        self.risk = RiskEstimatorSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        parsed = self.requirement.run(context)
        tasks = self.decomposer.run(context)
        criteria = self.criteria.run(context)
        risks = self.risk.run(context)
        return AgentResult(
            status="success",
            agent="P",
            summary="Planner created backlog and criteria.",
            findings=[
                {
                    "id": "P-001",
                    "severity": "low",
                    "message": f"Theme parsed as {parsed['theme']}",
                    "action": "Proceed to architecture design mapping.",
                }
            ],
            artifacts={
                "task_plan": {"parsed_requirements": parsed, "tasks": tasks, "risks": risks},
                "acceptance_criteria": criteria,
                "llm_connectivity": {
                    "RequirementParserSubAgent": True,
                    "TaskDecomposerSubAgent": True,
                    "AcceptanceCriteriaSubAgent": True,
                    "RiskEstimatorSubAgent": True,
                },
            },
            next_recommendation="Invoke architect phase.",
            context_version_out="v2",
        )
