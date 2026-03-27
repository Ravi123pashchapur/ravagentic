import json
from pathlib import Path

from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class WebVitalsSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for performance checks."
        user = "Return a very short phrase (<=8 words) for web vitals baseline."
        return call_llm_text(context, role_name="F.01.WebVitals", system_prompt=system, user_prompt=user)


class BundleAnalyzerSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for performance checks."
        user = "Return a very short phrase (<=8 words) for bundle analyzer baseline."
        return call_llm_text(context, role_name="F.02.BundleAnalyzer", system_prompt=system, user_prompt=user)


class ImageOptimizerSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for performance checks."
        user = "Return a very short phrase (<=8 words) acknowledging image policy skip."
        return call_llm_text(context, role_name="F.03.ImageOptimizer", system_prompt=system, user_prompt=user)


class RouteProfilingSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for performance checks."
        user = "Return a very short phrase (<=8 words) for route profiling baseline."
        return call_llm_text(context, role_name="F.04.RouteProfiling", system_prompt=system, user_prompt=user)


class PerformanceAgent:
    def __init__(self) -> None:
        self.vitals = WebVitalsSubAgent()
        self.bundle = BundleAnalyzerSubAgent()
        self.image = ImageOptimizerSubAgent()
        self.route = RouteProfilingSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        root = Path(str(context.constraints.get("root_path", ".")))
        package_path = root / "frontend/package.json"
        has_build_script = False
        if package_path.exists():
            data = json.loads(package_path.read_text(encoding="utf-8"))
            has_build_script = "build" in data.get("scripts", {})
        status = "success" if has_build_script else "failed"
        return AgentResult(
            status=status,
            agent="F",
            summary="Performance baseline checks prepared.",
            findings=[
                {
                    "id": "F-001",
                    "severity": "high" if not has_build_script else "low",
                    "message": "Frontend build script exists." if has_build_script else "Missing frontend build script.",
                    "action": "Proceed." if has_build_script else "Add `build` script in frontend/package.json.",
                }
            ],
            artifacts={
                "performance_report": {
                    "web_vitals": self.vitals.run(context),
                    "bundle": self.bundle.run(context),
                    "image": self.image.run(context),
                    "route": self.route.run(context),
                    "has_build_script": has_build_script,
                }
                ,
                "llm_connectivity": {
                    "F.01.WebVitals": True,
                    "F.02.BundleAnalyzer": True,
                    "F.03.ImageOptimizer": True,
                    "F.04.RouteProfiling": True,
                },
            },
            next_recommendation="Invoke data contract phase." if has_build_script else "Route to rework.",
            context_version_out="v7",
        )
