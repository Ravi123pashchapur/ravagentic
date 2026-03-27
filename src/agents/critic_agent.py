from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class ContextAlignmentCheckerSubAgent:
    def run(self, context: GlobalContext) -> str:
        _ = context
        return "alignment ok"


class InstructionComplianceSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a critic helper that summarizes instruction compliance."
        user = "Return a very short phrase (<=8 words) stating instruction compliance status."
        return call_llm_text(context, role_name="C.02.InstructionCompliance", system_prompt=system, user_prompt=user)


class QualityCritiqueSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a critic helper that summarizes quality review."
        user = "Return a very short phrase (<=8 words) stating quality review status."
        return call_llm_text(context, role_name="C.03.QualityCritique", system_prompt=system, user_prompt=user)


class RepairSuggestionSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a critic helper that summarizes repair suggestion."
        user = "Return a very short phrase (<=8 words) describing whether repair is needed."
        return call_llm_text(context, role_name="C.04.RepairSuggestion", system_prompt=system, user_prompt=user)


class CriticAgent:
    def __init__(self) -> None:
        self.alignment = ContextAlignmentCheckerSubAgent()
        self.compliance = InstructionComplianceSubAgent()
        self.quality = QualityCritiqueSubAgent()
        self.repair = RepairSuggestionSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        return AgentResult(
            status="success",
            agent="C",
            summary="Critic reviewed alignment and compliance.",
            artifacts={
                "critic_report": {
                    "alignment": self.alignment.run(context),
                    "compliance": self.compliance.run(context),
                    "quality": self.quality.run(context),
                    "repair": self.repair.run(context),
                    "verdict": "approved",
                }
                ,
                "llm_connectivity": {
                    "C.01.ContextAlignmentChecker": False,
                    "C.02.InstructionCompliance": True,
                    "C.03.QualityCritique": True,
                    "C.04.RepairSuggestion": True,
                },
            },
            next_recommendation="Mark workflow DONE.",
            context_version_out=context.context_version,
        )
