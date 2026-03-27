from .llm_client import call_llm_json
from .types import AgentResult, GlobalContext


class TemplateScoutSubAgent:
    def run(self, context: GlobalContext) -> list:
        system = "You suggest UI template/page categories for a themed dashboard."
        user = (
            "Return JSON with key \"templates\" as an array of 4 strings.\n"
            "The workflow must include these core pages: dashboard, profile, settings, landing.\n"
            "Return exactly those 4 strings in any order.\n"
            f"Theme: {context.user_theme_input.get('theme_name')}\n"
        )
        payload = call_llm_json(
            context,
            role_name="TemplateScoutSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        templates = payload.get("templates", [])
        return [str(t) for t in templates][:4]


class DesignSystemSubAgent:
    def run(self, context: GlobalContext) -> dict:
        palette = context.user_theme_input.get("palette", ["#111827", "#6366f1", "#f9fafb"])
        system = "You generate simple design tokens from a provided palette."
        user = (
            "Return JSON with key \"tokens\" having exactly: primary, accent, text.\n"
            f"Input palette: {palette}\n"
            "Use palette[0] for primary, palette[1] for accent, palette[2] for text.\n"
        )
        payload = call_llm_json(
            context,
            role_name="DesignSystemSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        tokens = payload.get("tokens", {})
        return {
            "primary": tokens.get("primary", palette[0]),
            "accent": tokens.get("accent", palette[1]),
            "text": tokens.get("text", palette[2]),
        }


class IntegrationBlueprintSubAgent:
    def run(self, context: GlobalContext) -> dict:
        expected = {
            "/": "GET /api/home",
            "/dashboard": "GET /api/dashboard",
            "/settings": "GET /api/settings",
            "/profile": "GET /api/profile",
        }
        system = "You create an API integration map for a fixed mock backend contract."
        user = (
            "Return JSON with key \"api_map\".\n"
            "api_map must map exactly these route keys to exactly these endpoint strings:\n"
            f"{expected}\n\n"
            "Return only the JSON."
        )
        payload = call_llm_json(
            context,
            role_name="IntegrationBlueprintSubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        api_map = payload.get("api_map", {})
        # Hard validation to keep DataContractAgent checks stable.
        if api_map != expected:
            raise RuntimeError(f"LLM api_map mismatch. Expected {expected}, got {api_map}")
        return api_map


class FolderStrategySubAgent:
    def run(self, context: GlobalContext) -> list:
        system = "You decide where key files should live in a Next.js app."
        user = (
            "Return JSON with key \"folders\" as an array of 3 strings.\n"
            "Use these exact folder paths:\n"
            "- frontend/src/app\n"
            "- frontend/src/lib/api\n"
            "- backend/src/routes\n"
            "Return only those exact values.\n"
        )
        payload = call_llm_json(
            context,
            role_name="FolderStrategySubAgent",
            system_prompt=system,
            user_prompt=user,
        )
        folders = payload.get("folders", [])
        expected = ["frontend/src/app", "frontend/src/lib/api", "backend/src/routes"]
        # Order doesn't matter for our usage, but validate membership.
        folders_norm = [str(f) for f in folders]
        if set(folders_norm) != set(expected):
            raise RuntimeError(f"LLM folders mismatch. Expected {expected}, got {folders_norm}")
        # Return expected order for stable markdown output
        return expected


class ArchitectAgent:
    def __init__(self) -> None:
        self.template = TemplateScoutSubAgent()
        self.design = DesignSystemSubAgent()
        self.blueprint = IntegrationBlueprintSubAgent()
        self.folder = FolderStrategySubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        api_map = self.blueprint.run(context)
        return AgentResult(
            status="success",
            agent="A",
            summary="Architect produced design and contract blueprint.",
            findings=[
                {
                    "id": "A-001",
                    "severity": "low",
                    "message": f"Defined {len(api_map)} route-to-endpoint mappings.",
                    "action": "Proceed to build implementation alignment.",
                }
            ],
            artifacts={
                "architecture_spec": {
                    "templates": self.template.run(context),
                    "design_tokens": self.design.run(context),
                    "api_map": api_map,
                    "folders": self.folder.run(context),
                },
                "llm_connectivity": {
                    "TemplateScoutSubAgent": True,
                    "DesignSystemSubAgent": True,
                    "IntegrationBlueprintSubAgent": True,
                    "FolderStrategySubAgent": True,
                },
            },
            next_recommendation="Invoke build phase.",
            context_version_out="v3",
        )
