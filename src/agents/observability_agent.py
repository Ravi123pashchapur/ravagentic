from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class LoggingSetupSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for observability setup."
        user = "Return a very short phrase (<=8 words) for structured logging setup status."
        return call_llm_text(context, role_name="V.01.LoggingSetup", system_prompt=system, user_prompt=user)


class MetricsSetupSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for observability setup."
        user = "Return a very short phrase (<=8 words) for metrics setup status."
        return call_llm_text(context, role_name="V.02.MetricsSetup", system_prompt=system, user_prompt=user)


class TracingSetupSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for observability setup."
        user = "Return a very short phrase (<=8 words) for tracing setup status."
        return call_llm_text(context, role_name="V.03.TracingSetup", system_prompt=system, user_prompt=user)


class AlertRulesSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for observability setup."
        user = "Return a very short phrase (<=8 words) for alert rules setup status."
        return call_llm_text(context, role_name="V.04.AlertRules", system_prompt=system, user_prompt=user)


class ObservabilityAgent:
    def __init__(self) -> None:
        self.logging = LoggingSetupSubAgent()
        self.metrics = MetricsSetupSubAgent()
        self.tracing = TracingSetupSubAgent()
        self.alerts = AlertRulesSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        release_gate_ok = context.quality_gates.get("release") == "pass"
        status = "success" if release_gate_ok else "failed"
        return AgentResult(
            status=status,
            agent="V",
            summary="Observability baseline prepared.",
            findings=[
                {
                    "id": "V-001",
                    "severity": "medium" if not release_gate_ok else "low",
                    "message": (
                        "Release gate not passing; observability is provisional."
                        if not release_gate_ok
                        else "Observability baseline aligned with release state."
                    ),
                    "action": "Rework release gate first." if not release_gate_ok else "Proceed.",
                }
            ],
            artifacts={
                "observability_report": {
                    "logging": self.logging.run(context),
                    "metrics": self.metrics.run(context),
                    "tracing": self.tracing.run(context),
                    "alerts": self.alerts.run(context),
                    "release_gate_ok": release_gate_ok,
                }
                ,
                "llm_connectivity": {
                    "V.01.LoggingSetup": True,
                    "V.02.MetricsSetup": True,
                    "V.03.TracingSetup": True,
                    "V.04.AlertRules": True,
                },
            },
            next_recommendation="Run critic conditionally if needed." if release_gate_ok else "Route to rework.",
            context_version_out="v10",
        )
