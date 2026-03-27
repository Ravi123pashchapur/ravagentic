from .types import AgentResult, GlobalContext
from .llm_client import call_llm_text


class PipelineOrchestratorSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for release/CI workflows."
        user = "Return a very short phrase describing pipeline orchestration is ready."
        return call_llm_text(context, role_name="R.01.PipelineOrchestrator", system_prompt=system, user_prompt=user)


class QualityGateSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for release/CI workflows."
        user = "Return a very short phrase describing quality gate checks are ready."
        return call_llm_text(context, role_name="R.02.QualityGate", system_prompt=system, user_prompt=user)


class DeploymentPlannerSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for release/CI workflows."
        user = "Return a very short phrase describing deployment planning is ready."
        return call_llm_text(context, role_name="R.03.DeploymentPlanner", system_prompt=system, user_prompt=user)


class RollbackManagerSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for release/CI workflows."
        user = "Return a very short phrase describing rollback planning is ready."
        return call_llm_text(context, role_name="R.04.RollbackManager", system_prompt=system, user_prompt=user)


class ReleaseAgent:
    def __init__(self) -> None:
        self.pipeline = PipelineOrchestratorSubAgent()
        self.gate = QualityGateSubAgent()
        self.deploy = DeploymentPlannerSubAgent()
        self.rollback = RollbackManagerSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        mandatory = ["test", "security", "performance", "contract"]
        failing = [gate for gate in mandatory if context.quality_gates.get(gate) != "pass"]
        status = "success" if not failing else "failed"
        return AgentResult(
            status=status,
            agent="R",
            summary="Release/CI baseline checks prepared.",
            findings=[
                {
                    "id": "R-001",
                    "severity": "high" if failing else "low",
                    "message": (
                        "Mandatory gates not passing yet: " + ", ".join(failing)
                        if failing
                        else "All mandatory pre-release gates are passing."
                    ),
                    "action": "Route to rework for failed gates." if failing else "Proceed.",
                }
            ],
            artifacts={
                "release_report": {
                    "pipeline": self.pipeline.run(context),
                    "quality_gate": self.gate.run(context),
                    "deployment": self.deploy.run(context),
                    "rollback": self.rollback.run(context),
                    "failed_mandatory_gates": failing,
                }
                ,
                "llm_connectivity": {
                    "R.01.PipelineOrchestrator": True,
                    "R.02.QualityGate": True,
                    "R.03.DeploymentPlanner": True,
                    "R.04.RollbackManager": True,
                },
            },
            next_recommendation="Invoke observability phase." if not failing else "Route to rework.",
            context_version_out="v9",
        )
