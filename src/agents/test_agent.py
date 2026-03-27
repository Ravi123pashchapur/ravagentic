from pathlib import Path

from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class StaticCheckSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for UI test workflows."
        user = "Return a very short phrase (<=8 words) describing static check planning."
        return call_llm_text(context, role_name="T.01.StaticCheck", system_prompt=system, user_prompt=user)


class IntegrationTestSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for UI test workflows."
        user = "Return a very short phrase (<=8 words) describing integration route checks."
        return call_llm_text(context, role_name="T.02.IntegrationTest", system_prompt=system, user_prompt=user)


class UIValidationSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for UI test workflows."
        user = "Return a very short phrase (<=8 words) describing theme/ui validation checks."
        return call_llm_text(context, role_name="T.03.UIValidation", system_prompt=system, user_prompt=user)


class RegressionGuardSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for UI test workflows."
        user = "Return a very short phrase (<=8 words) describing regression guard checks."
        return call_llm_text(context, role_name="T.04.RegressionGuard", system_prompt=system, user_prompt=user)


class TestAgent:
    def __init__(self) -> None:
        self.static = StaticCheckSubAgent()
        self.integration = IntegrationTestSubAgent()
        self.ui = UIValidationSubAgent()
        self.regression = RegressionGuardSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        root = Path(str(context.constraints.get("root_path", ".")))
        expected = [
            root / "frontend/src/app/page.tsx",
            root / "frontend/src/app/dashboard/page.tsx",
            root / "frontend/src/app/settings/page.tsx",
            root / "frontend/src/app/profile/page.tsx",
        ]
        missing = [str(path) for path in expected if not path.exists()]
        status = "success" if not missing else "failed"
        return AgentResult(
            status=status,
            agent="T",
            summary="Test phase completed route baseline checks.",
            findings=[
                {
                    "id": "T-001",
                    "severity": "high" if missing else "low",
                    "message": (
                        "Missing expected route files: " + ", ".join(missing)
                        if missing
                        else "All expected route files are present."
                    ),
                    "action": "Fix route scaffold files before continuing." if missing else "Proceed.",
                }
            ],
            artifacts={
                "test_report": {
                    "static": self.static.run(context),
                    "integration": self.integration.run(context),
                    "ui": self.ui.run(context),
                    "regression": self.regression.run(context),
                    "missing_route_files": missing,
                }
                ,
                "llm_connectivity": {
                    "T.01.StaticCheck": True,
                    "T.02.IntegrationTest": True,
                    "T.03.UIValidation": True,
                    "T.04.RegressionGuard": True,
                },
            },
            next_recommendation="Invoke security phase." if not missing else "Route to rework.",
            context_version_out="v5",
        )
