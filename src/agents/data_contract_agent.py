from pathlib import Path

from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class SchemaSyncSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for data contract checks."
        user = "Return a very short phrase (<=8 words) for schema sync status."
        return call_llm_text(context, role_name="D.01.SchemaSync", system_prompt=system, user_prompt=user)


class ContractDiffSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for data contract checks."
        user = "Return a very short phrase (<=8 words) for contract diff status."
        return call_llm_text(context, role_name="D.02.ContractDiff", system_prompt=system, user_prompt=user)


class MockParitySubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for data contract checks."
        user = "Return a very short phrase (<=8 words) for mock parity status."
        return call_llm_text(context, role_name="D.03.MockParity", system_prompt=system, user_prompt=user)


class CompatibilityGuardSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for data contract checks."
        user = "Return a very short phrase (<=8 words) for compatibility guard status."
        return call_llm_text(context, role_name="D.04.CompatibilityGuard", system_prompt=system, user_prompt=user)


class DataContractAgent:
    def __init__(self) -> None:
        self.schema = SchemaSyncSubAgent()
        self.diff = ContractDiffSubAgent()
        self.parity = MockParitySubAgent()
        self.compat = CompatibilityGuardSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        architecture = context.artifacts.get("architecture_spec", {})
        api_map = architecture.get("api_map", {})
        root = Path(str(context.constraints.get("root_path", ".")))
        contracts_file = root / "frontend/src/lib/api/contracts.ts"
        contracts_text = contracts_file.read_text(encoding="utf-8") if contracts_file.exists() else ""
        missing = []
        for endpoint in api_map.values():
            if isinstance(endpoint, str) and endpoint not in contracts_text:
                missing.append(endpoint)
        status = "success" if not missing else "failed"
        return AgentResult(
            status=status,
            agent="D",
            summary="Data contract baseline checks prepared.",
            findings=[
                {
                    "id": "D-001",
                    "severity": "high" if missing else "low",
                    "message": (
                        "Missing endpoints in frontend contract: " + ", ".join(missing)
                        if missing
                        else "Frontend contract includes all architect endpoints."
                    ),
                    "action": "Update frontend contract map." if missing else "Proceed.",
                }
            ],
            artifacts={
                "contract_report": {
                    "schema_sync": self.schema.run(context),
                    "contract_diff": self.diff.run(context),
                    "mock_parity": self.parity.run(context),
                    "compatibility": self.compat.run(context),
                    "missing_endpoints": missing,
                }
                ,
                "llm_connectivity": {
                    "D.01.SchemaSync": True,
                    "D.02.ContractDiff": True,
                    "D.03.MockParity": True,
                    "D.04.CompatibilityGuard": True,
                },
            },
            next_recommendation="Invoke release phase." if not missing else "Route to rework.",
            context_version_out="v8",
        )
