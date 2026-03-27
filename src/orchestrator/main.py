import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.architect_agent import ArchitectAgent
from agents.build_agent import BuildAgent
from agents.critic_agent import CriticAgent
from agents.data_contract_agent import DataContractAgent
from agents.observability_agent import ObservabilityAgent
from agents.orchestrator_agent import OrchestratorAgent
from agents.performance_agent import PerformanceAgent
from agents.planner_agent import PlannerAgent
from agents.release_agent import ReleaseAgent
from agents.security_agent import SecurityAgent
from agents.test_agent import TestAgent
from agents.types import AgentResult, GlobalContext


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ravgentic canonical orchestrator")
    parser.add_argument("--auto-validate", action="store_true")
    parser.add_argument("--ui-prompt", type=str, default="")
    parser.add_argument("--theme", type=str, default="")
    parser.add_argument("--keywords", type=str, default="")
    parser.add_argument("--palette", type=str, default="")
    parser.add_argument("--theme-file", type=str, default="")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    return parser.parse_args()


def parse_csv_list(raw_value: str) -> List[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def resolve_output_dir(root: Path, output_dir_arg: str) -> Path:
    if output_dir_arg.strip().lower() == "auto":
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return root / "artifacts" / "runs" / timestamp
    candidate = Path(output_dir_arg)
    return candidate if candidate.is_absolute() else root / candidate


def prompt_theme() -> Dict[str, Any]:
    ui_prompt = input("Desired UI themed prompt: ").strip()
    theme_name = input("Theme name: ").strip() or "modern-dark"
    keywords_raw = input("Style keywords (comma-separated): ").strip()
    palette_raw = input("Palette colors (comma-separated hex): ").strip()
    keywords = parse_csv_list(keywords_raw) or ["minimal", "clean", "responsive"]
    palette = parse_csv_list(palette_raw) or ["#111827", "#6366f1", "#f9fafb"]
    return {
        "ui_prompt": ui_prompt,
        "theme_name": theme_name,
        "style_keywords": keywords,
        "palette": palette,
        "layout_preferences": ["dashboard", "responsive", "mobile-first"],
    }


def theme_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "ui_prompt": args.ui_prompt.strip(),
        "theme_name": args.theme.strip() or "modern-dark",
        "style_keywords": parse_csv_list(args.keywords) or ["minimal", "clean", "responsive"],
        "palette": parse_csv_list(args.palette) or ["#111827", "#6366f1", "#f9fafb"],
        "layout_preferences": ["dashboard", "responsive", "mobile-first"],
    }


def theme_from_file(theme_file_path: str, root: Path) -> Dict[str, Any]:
    path = Path(theme_file_path)
    if not path.is_absolute():
        path = root / path
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_keywords = data.get("style_keywords", [])
    raw_palette = data.get("palette", [])
    keywords = (
        [str(k).strip() for k in raw_keywords if str(k).strip()]
        if isinstance(raw_keywords, list)
        else parse_csv_list(str(raw_keywords))
    )
    palette = (
        [str(c).strip() for c in raw_palette if str(c).strip()]
        if isinstance(raw_palette, list)
        else parse_csv_list(str(raw_palette))
    )
    return {
        "ui_prompt": str(data.get("ui_prompt", "")).strip(),
        "theme_name": str(data.get("theme_name", "")).strip() or "modern-dark",
        "style_keywords": keywords or ["minimal", "clean", "responsive"],
        "palette": palette or ["#111827", "#6366f1", "#f9fafb"],
        "layout_preferences": data.get("layout_preferences", ["dashboard", "responsive", "mobile-first"]),
    }


def resolve_theme_input(args: argparse.Namespace, root: Path) -> Dict[str, Any]:
    if args.theme_file.strip():
        print("Input mode: non-interactive (theme file)")
        return theme_from_file(args.theme_file.strip(), root)
    if args.ui_prompt.strip() or args.theme.strip() or args.keywords.strip() or args.palette.strip():
        print("Input mode: non-interactive (CLI args)")
        return theme_from_args(args)
    print("Input mode: interactive")
    return prompt_theme()


def load_env_file(root: Path) -> Dict[str, str]:
    env_path = root / ".env"
    if not env_path.exists():
        return {}
    parsed: Dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def build_context(theme_input: Dict[str, Any]) -> GlobalContext:
    root = Path(__file__).resolve().parents[2]
    env = load_env_file(root)
    return GlobalContext(
        session_id=f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        project="m2r2",
        user_theme_input=theme_input,
        memory={
            "working": {},
            "episodic": [],
            "semantic": {},
            "tool_names": [],
        },
        requirements={
            "frontend_framework": "nextjs",
            "backend_mode": "mock-backend",
            "must_connect_backend": True,
            "reference_template_path": env.get("REFERENCE_TEMPLATE_PATH", ""),
            "reference_mode": env.get("REFERENCE_MODE", "inspiration_only"),
            "copy_mode": env.get("COPY_MODE", "forbidden"),
            "openai_api_key": env.get("OPENAI_API_KEY", ""),
            "openai_model": env.get("OPENAI_MODEL", "gpt-5.1"),
        },
        constraints={"accessibility_level": "WCAG-AA", "root_path": str(root)},
        acceptance_criteria=[
            "Theme reflected across core pages",
            "Frontend successfully consumes mock backend endpoints",
            "Build and tests pass",
        ],
        quality_gates={
            "test": "pending",
            "security": "pending",
            "performance": "pending",
            "contract": "pending",
            "release": "pending",
            "observability": "pending",
            "critic": "skipped",
        },
        context_version="v1",
    )


def write_markdown_artifacts(context: GlobalContext, artifacts_dir: Path) -> None:
    task_plan = context.artifacts.get("task_plan", {})
    architecture_spec = context.artifacts.get("architecture_spec", {})
    api_map = architecture_spec.get("api_map", {})

    task_md = (
        "# Task Plan\n\n"
        "## Parsed Requirements\n"
        f"- Theme: {task_plan.get('parsed_requirements', {}).get('theme', 'n/a')}\n\n"
        "## Tasks\n"
        + "\n".join([f"- {t}" for t in task_plan.get("tasks", [])])
        + "\n\n## Risks\n"
        + "\n".join([f"- {r}" for r in task_plan.get("risks", [])])
        + "\n"
    )
    arch_md = (
        "# Architecture Spec\n\n"
        f"Theme: `{context.user_theme_input.get('theme_name', 'n/a')}`\n\n"
        "## Design Tokens\n"
        + "\n".join(
            [
                f"- {k}: `{v}`"
                for k, v in architecture_spec.get("design_tokens", {}).items()
            ]
        )
        + "\n\n## Templates\n"
        + "\n".join([f"- {t}" for t in architecture_spec.get("templates", [])])
        + "\n\n## Folder Strategy\n"
        + "\n".join([f"- {f}" for f in architecture_spec.get("folders", [])])
        + "\n"
    )

    (artifacts_dir / "theme_input.json").write_text(
        json.dumps(context.user_theme_input, indent=2),
        encoding="utf-8",
    )
    (artifacts_dir / "task_plan.md").write_text(task_md, encoding="utf-8")
    (artifacts_dir / "architecture_spec.md").write_text(arch_md, encoding="utf-8")
    normalized_contract_map: Dict[str, Dict[str, Any]] = {}
    default_response_keys = {
        "/": {"headline": "string", "highlights": "string[]"},
        "/dashboard": {"stats": "object[]", "notifications": "object[]"},
        "/settings": {"preferences": "object", "flags": "object"},
        "/profile": {"user": "object", "activity": "object[]"},
    }
    for route, value in api_map.items():
        if isinstance(value, str):
            normalized_contract_map[route] = {
                "endpoint": value,
                "response_schema": default_response_keys.get(route, {"data": "object"}),
                "error_schema": {"message": "string", "code": "string"},
            }
        elif isinstance(value, dict):
            normalized_contract_map[route] = value
    (artifacts_dir / "api_contract_map.json").write_text(
        json.dumps(normalized_contract_map, indent=2),
        encoding="utf-8",
    )


def run_phase5_validation(root: Path, artifacts_dir: Path) -> bool:
    result = subprocess.run(
        ["python3", "src/validation/run_phase5.py", "--artifacts-dir", str(artifacts_dir)],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print("\nPhase-5 validation output:")
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(result.stderr.strip())
    return result.returncode == 0


def update_runs_index(root: Path, artifacts_dir: Path, context: GlobalContext, validation_status: str) -> None:
    runs_dir = root / "artifacts" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    index_path = runs_dir / "index.json"
    if index_path.exists():
        try:
            runs = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(runs, list):
                runs = []
        except json.JSONDecodeError:
            runs = []
    else:
        runs = []
    runs.insert(
        0,
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "session_id": context.session_id,
            "artifacts_dir": str(artifacts_dir),
            "theme_name": context.user_theme_input.get("theme_name"),
            "validation_status": validation_status,
            "context_version": context.context_version,
        },
    )
    index_path.write_text(json.dumps(runs[:200], indent=2), encoding="utf-8")


def run_pipeline(context: GlobalContext) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    context.artifacts["rework_summary"] = {
        "initial_failed_gates": [],
        "targeted_steps_executed": [],
        "post_rework_failed_gates": [],
    }
    steps: List = [
        OrchestratorAgent().refine_prompt,
        OrchestratorAgent().init_context,
        PlannerAgent().run,
        ArchitectAgent().run,
        BuildAgent().run,
        TestAgent().run,
        SecurityAgent().run,
        PerformanceAgent().run,
        DataContractAgent().run,
        ReleaseAgent().run,
        ObservabilityAgent().run,
    ]
    gate_by_agent = {
        "T": "test",
        "S": "security",
        "F": "performance",
        "D": "contract",
        "R": "release",
        "V": "observability",
    }
    for step in steps:
        result = normalize_agent_result(step(context), context.context_version)
        context.context_version = result.context_version_out
        context.artifacts.update(result.artifacts)
        gate = gate_by_agent.get(result.agent)
        if gate:
            context.quality_gates[gate] = "pass" if result.status == "success" else "fail"
        results.append(result.__dict__)
    mandatory_failed = failed_mandatory_gates(context)
    if mandatory_failed:
        context.artifacts["rework_summary"]["initial_failed_gates"] = mandatory_failed
        run_rework_loop(context, results, max_loops=1)
        mandatory_failed = failed_mandatory_gates(context)
        context.artifacts["rework_summary"]["post_rework_failed_gates"] = mandatory_failed
    if mandatory_failed:
        critic = normalize_agent_result(CriticAgent().run(context), context.context_version)
        context.artifacts.update(critic.artifacts)
        context.quality_gates["critic"] = critic.artifacts.get("critic_report", {}).get("verdict", "blocked")
        results.append(critic.__dict__)
    return results


def normalize_agent_result(result: AgentResult, fallback_version: str) -> AgentResult:
    normalized_status = result.status if result.status in {"success", "failed", "blocked"} else "failed"
    normalized_findings: List[Dict[str, str]] = []
    for finding in result.findings:
        normalized_findings.append(
            {
                "id": str(finding.get("id", "UNSPECIFIED")),
                "severity": str(finding.get("severity", "low")).lower(),
                "message": str(finding.get("message", "")),
                "action": str(finding.get("action", "")),
            }
        )
    result.status = normalized_status
    result.findings = normalized_findings
    if not result.context_version_out:
        result.context_version_out = fallback_version
    return result


def failed_mandatory_gates(context: GlobalContext) -> List[str]:
    mandatory = ["test", "security", "performance", "contract", "release", "observability"]
    return [gate for gate in mandatory if context.quality_gates.get(gate) == "fail"]


def run_rework_loop(context: GlobalContext, results: List[Dict[str, Any]], max_loops: int = 1) -> None:
    all_rework_steps: Dict[str, Any] = {
        "build": BuildAgent().run,
        "test": TestAgent().run,
        "security": SecurityAgent().run,
        "performance": PerformanceAgent().run,
        "contract": DataContractAgent().run,
        "release": ReleaseAgent().run,
        "observability": ObservabilityAgent().run,
    }
    dependency_chain = ["test", "security", "performance", "contract", "release", "observability"]

    def targeted_step_keys(failed_gates: List[str]) -> List[str]:
        keys = {"build"}
        for gate in failed_gates:
            if gate in dependency_chain:
                idx = dependency_chain.index(gate)
                keys.update(dependency_chain[idx:])
        ordered = ["build"] + [g for g in dependency_chain if g in keys]
        return ordered
    gate_by_agent = {
        "T": "test",
        "S": "security",
        "F": "performance",
        "D": "contract",
        "R": "release",
        "V": "observability",
    }
    for _ in range(max_loops):
        failed = failed_mandatory_gates(context)
        if not failed:
            break
        targeted = targeted_step_keys(failed)
        context.artifacts["rework_summary"]["targeted_steps_executed"].extend(targeted)
        for key in targeted:
            step = all_rework_steps[key]
            result = normalize_agent_result(step(context), context.context_version)
            context.context_version = result.context_version_out
            context.artifacts.update(result.artifacts)
            gate = gate_by_agent.get(result.agent)
            if gate:
                context.quality_gates[gate] = "pass" if result.status == "success" else "fail"
            result.next_recommendation = f"REWORK_TARGETED_{key.upper()}"
            results.append(result.__dict__)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    artifacts_dir = resolve_output_dir(root, args.output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=== ravgentic Canonical Orchestrator ===")
    theme_input = resolve_theme_input(args, root)
    context = build_context(theme_input)

    results = run_pipeline(context)
    write_markdown_artifacts(context, artifacts_dir)

    validation_status = "not_run"
    if args.auto_validate:
        ok = run_phase5_validation(root, artifacts_dir)
        validation_status = "pass" if ok else "fail"
        print(f"\nAuto-validation status: {'PASS' if ok else 'FAIL'}")

    orchestrator_log = {
        "session_id": context.session_id,
        "context_version": context.context_version,
        "quality_gates": context.quality_gates,
        "final_state": "REWORK" if "fail" in context.quality_gates.values() else "DONE",
        "reason_codes": [
            f"GATE_FAIL_{gate.upper()}"
            for gate, status in context.quality_gates.items()
            if status == "fail"
        ],
        "results": results,
        "artifacts": context.artifacts,
    }
    (artifacts_dir / "orchestrator_run_log.json").write_text(
        json.dumps(orchestrator_log, indent=2),
        encoding="utf-8",
    )
    update_runs_index(root, artifacts_dir, context, validation_status)

    print(f"\nSaved artifacts in: {artifacts_dir}")
    print("- theme_input.json")
    print("- task_plan.md")
    print("- architecture_spec.md")
    print("- api_contract_map.json")
    print("- orchestrator_run_log.json")
    print(f"Run indexed at: {root / 'artifacts' / 'runs' / 'index.json'}")


if __name__ == "__main__":
    main()
