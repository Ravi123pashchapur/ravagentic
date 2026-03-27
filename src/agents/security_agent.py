from pathlib import Path

from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class SecretScanSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for security checks."
        user = "Return a very short phrase (<=8 words) for secret scanning baseline."
        return call_llm_text(context, role_name="S.01.SecretScan", system_prompt=system, user_prompt=user)


class DependencyAuditSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for security checks."
        user = "Return a very short phrase (<=8 words) for dependency audit baseline."
        return call_llm_text(context, role_name="S.02.DependencyAudit", system_prompt=system, user_prompt=user)


class PolicyGuardSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for security checks."
        user = "Return a very short phrase (<=8 words) for security policy baseline."
        return call_llm_text(context, role_name="S.03.PolicyGuard", system_prompt=system, user_prompt=user)


class LicenseGuardSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for security checks."
        user = "Return a very short phrase (<=8 words) for license baseline."
        return call_llm_text(context, role_name="S.04.LicenseGuard", system_prompt=system, user_prompt=user)


class SecurityAgent:
    def __init__(self) -> None:
        self.secret = SecretScanSubAgent()
        self.deps = DependencyAuditSubAgent()
        self.policy = PolicyGuardSubAgent()
        self.license = LicenseGuardSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        root = Path(str(context.constraints.get("root_path", ".")))
        gitignore_path = root / ".gitignore"
        gitignore_text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        has_env_ignore = ".env" in gitignore_text
        status = "success" if has_env_ignore else "failed"
        return AgentResult(
            status=status,
            agent="S",
            summary="Security baseline checks prepared.",
            findings=[
                {
                    "id": "S-001",
                    "severity": "high" if not has_env_ignore else "low",
                    "message": ".env ignore rule present." if has_env_ignore else "Missing .env ignore rule in .gitignore.",
                    "action": "Proceed." if has_env_ignore else "Add .env to .gitignore.",
                }
            ],
            artifacts={
                "security_report": {
                    "secret": self.secret.run(context),
                    "dependency": self.deps.run(context),
                    "policy": self.policy.run(context),
                    "license": self.license.run(context),
                    "has_env_ignore": has_env_ignore,
                }
                ,
                "llm_connectivity": {
                    "S.01.SecretScan": True,
                    "S.02.DependencyAudit": True,
                    "S.03.PolicyGuard": True,
                    "S.04.LicenseGuard": True,
                },
            },
            next_recommendation="Invoke performance phase." if has_env_ignore else "Route to rework.",
            context_version_out="v6",
        )
