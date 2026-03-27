import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

    reference_template_path = theme_input.get("reference_template_path", "")
    if not reference_template_path:
        reference_template_path = env.get("REFERENCE_TEMPLATE_PATH", "")

    reference_mode = theme_input.get("reference_mode", env.get("REFERENCE_MODE", "inspiration_only"))
    copy_mode = theme_input.get("copy_mode", env.get("COPY_MODE", "forbidden"))

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
            "reference_template_path": reference_template_path,
            "reference_mode": reference_mode,
            "copy_mode": copy_mode,
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


def targeted_step_keys(failed_gates: List[str]) -> List[str]:
    dependency_chain = ["test", "security", "performance", "contract", "release", "observability"]

    keys = {"build"}
    for gate in failed_gates:
        if gate in dependency_chain:
            idx = dependency_chain.index(gate)
            keys.update(dependency_chain[idx:])

    ordered = ["build"] + [g for g in dependency_chain if g in keys]
    return ordered


GATE_BY_AGENT = {
    "T": "test",
    "S": "security",
    "F": "performance",
    "D": "contract",
    "R": "release",
    "V": "observability",
}

STAGE_TO_GATE = {
    "B": "build",
    "T": "test",
    "S": "security",
    "F": "performance",
    "D": "contract",
    "R": "release",
    "V": "observability",
}

GATE_TO_STAGE = {v: k for k, v in STAGE_TO_GATE.items()}


def load_state(state_path: Path) -> Dict[str, Any]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def stage_handlers() -> Dict[str, List[Tuple[str, Any]]]:
    """
    Returns stage_id -> list of (response_agent_label, callable(context)->AgentResult)
    The response_agent_label is used only for UI clarity; AgentResult.agent already exists.
    """
    return {
        "O": [
            ("O", OrchestratorAgent().refine_prompt),
            ("O", OrchestratorAgent().init_context),
        ],
        "P": [("P", PlannerAgent().run)],
        "A": [("A", ArchitectAgent().run)],
        "B": [("B", BuildAgent().run)],
        "T": [("T", TestAgent().run)],
        "S": [("S", SecurityAgent().run)],
        "F": [("F", PerformanceAgent().run)],
        "D": [("D", DataContractAgent().run)],
        "R": [("R", ReleaseAgent().run)],
        "V": [("V", ObservabilityAgent().run)],
        "C": [("C", CriticAgent().run)],
    }


MAIN_STAGE_ORDER = ["O", "P", "A", "B", "T", "S", "F", "D", "R", "V"]


def context_from_dict(context_dict: Dict[str, Any]) -> GlobalContext:
    # GlobalContext artifacts/quality_gates are optional in the dict.
    return GlobalContext(**context_dict)


def agent_result_to_json(result: AgentResult) -> Dict[str, Any]:
    return result.__dict__


def build_stage_event(
    session_id: str,
    done: bool,
    stage_id: str,
    stage_name: str,
    stage_summary: str,
    responses: List[Dict[str, Any]],
    final_state: str = "",
    quality_gates: Any = None,
) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "done": done,
        "final_state": final_state,
        "quality_gates": quality_gates or {},
        "stage": {
            "stage_id": stage_id,
            "stage_name": stage_name,
            "summary": stage_summary,
            "responses": responses,
        },
    }


def execute_one_stage(state: Dict[str, Any], decision: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Executes exactly one stage based on state and returns (event, updated_state).
    """
    context = context_from_dict(state["context"])
    session_id = state["session_id"]
    mode = state["mode"]

    if decision != "approve":
        # For now, we ignore other decisions and continue; UI handles stop by not calling this endpoint.
        pass

    stage_id = None
    stage_name = ""
    stage_summary = ""
    responses_json: List[Dict[str, Any]] = []

    handlers = stage_handlers()

    def run_response(callable_fn, context: GlobalContext) -> AgentResult:
        result = normalize_agent_result(callable_fn(context), context.context_version)
        context.context_version = result.context_version_out
        context.artifacts.update(result.artifacts)
        gate = GATE_BY_AGENT.get(result.agent)
        if gate:
            context.quality_gates[gate] = "pass" if result.status == "success" else "fail"
        return result

    if mode == "main":
        idx = int(state.get("main_stage_index", 0))
        if idx >= len(MAIN_STAGE_ORDER):
            # Should not happen; treat as done.
            done_event = build_stage_event(
                session_id=session_id,
                done=True,
                stage_id="",
                stage_name="",
                stage_summary="",
                responses=[],
                final_state="DONE",
                quality_gates=context.quality_gates,
            )
            return done_event, state

        stage_id = MAIN_STAGE_ORDER[idx]
        stage_name = f"Main Agent {stage_id}"

        # For UI, we show stage completion, but we still run any sub-calls within the stage.
        for _, fn in handlers[stage_id]:
            try:
                result = run_response(fn, context)
            except Exception as e:
                # Convert errors into a structured failure event so the UI can display it.
                err_text = str(e)
                failed_agent_result = AgentResult(
                    status="failed",
                    agent=stage_id,
                    summary=f"Stage {stage_id} failed: {err_text[:200]}",
                    findings=[
                        {
                            "id": f"{stage_id}-ERR",
                            "severity": "high",
                            "message": err_text,
                            "action": "Human approval required to proceed or fix OPENAI_API_KEY/LLM output.",
                        }
                    ],
                    artifacts={},
                    next_recommendation="Human_review_required",
                    context_version_out=context.context_version,
                )
                result = failed_agent_result
                responses_json.append(agent_result_to_json(result))
                state["results"].append(agent_result_to_json(result))
                # Pause immediately on error.
                done = False
                state["mode"] = "error"
                state["context"] = context.__dict__
                event = build_stage_event(
                    session_id=session_id,
                    done=False,
                    stage_id=stage_id,
                    stage_name=stage_name,
                    stage_summary=f"Error in stage {stage_id}.",
                    responses=responses_json,
                    final_state="",
                    quality_gates=context.quality_gates,
                )
                return event, state

            responses_json.append(agent_result_to_json(result))
            state["results"].append(agent_result_to_json(result))

        state["main_stage_index"] = idx + 1

        # After V stage, decide whether we need rework.
        if stage_id == "V":
            mandatory_failed = failed_mandatory_gates(context)
            if mandatory_failed:
                state["mode"] = "rework"
                state["rework_loop"] = int(state.get("rework_loop", 0))
                state["rework_stage_queue_gates"] = targeted_step_keys(mandatory_failed)

                ctx_artifacts = context.artifacts
                ctx_artifacts.setdefault(
                    "rework_summary",
                    {"initial_failed_gates": [], "targeted_steps_executed": [], "post_rework_failed_gates": []},
                )
                ctx_artifacts["rework_summary"]["initial_failed_gates"] = mandatory_failed
                ctx_artifacts["rework_summary"]["targeted_steps_executed"].extend(state["rework_stage_queue_gates"])

                state["rework_stage_queue"] = [GATE_TO_STAGE[g] for g in state["rework_stage_queue_gates"] if g in GATE_TO_STAGE]
                state["rework_stage_index"] = 0
                stage_summary = "Mandatory gates failed; awaiting rework (human approval to continue)."
                done = False
            else:
                stage_summary = "All mandatory gates passed."
                state["mode"] = "done"
                done = True
        else:
            stage_summary = f"Completed stage {stage_id}. Awaiting human review."
            done = False

    elif mode == "rework":
        queue = state.get("rework_stage_queue", [])
        idx = int(state.get("rework_stage_index", 0))
        if idx >= len(queue):
            # Decide next (critic or done).
            mandatory_failed = failed_mandatory_gates(context)
            if mandatory_failed:
                context.artifacts.setdefault(
                    "rework_summary",
                    {"initial_failed_gates": [], "targeted_steps_executed": [], "post_rework_failed_gates": []},
                )
                context.artifacts["rework_summary"]["post_rework_failed_gates"] = mandatory_failed
                state["mode"] = "critic"
                stage_id = "C"
                stage_name = "Critic"
                stage_summary = "Rework incomplete; awaiting critic (human approval)."
                done = False
                # Do not execute critic here; pause for human approval.
                done_event = build_stage_event(
                    session_id=session_id,
                    done=done,
                    stage_id=stage_id,
                    stage_name=stage_name,
                    stage_summary=stage_summary,
                    responses=[],
                    final_state="",
                    quality_gates=context.quality_gates,
                )
                return done_event, state

            state["mode"] = "done"
            stage_summary = "Rework complete; all mandatory gates passed."
            done = True
            done_event = build_stage_event(
                session_id=session_id,
                done=done,
                stage_id="",
                stage_name="",
                stage_summary=stage_summary,
                responses=[],
                final_state="DONE",
                quality_gates=context.quality_gates,
            )
            return done_event, state

        stage_id = queue[idx]
        stage_name = f"Rework Agent {stage_id}"

        for _, fn in handlers[stage_id]:
            try:
                result = run_response(fn, context)
            except Exception as e:
                err_text = str(e)
                failed_agent_result = AgentResult(
                    status="failed",
                    agent=stage_id,
                    summary=f"Rework stage {stage_id} failed: {err_text[:200]}",
                    findings=[
                        {
                            "id": f"{stage_id}-ERR",
                            "severity": "high",
                            "message": err_text,
                            "action": "Human review required.",
                        }
                    ],
                    artifacts={},
                    next_recommendation="Human_review_required",
                    context_version_out=context.context_version,
                )
                result = failed_agent_result
                responses_json.append(agent_result_to_json(result))
                state["results"].append(agent_result_to_json(result))
                done = False
                state["mode"] = "error"
                state["context"] = context.__dict__
                event = build_stage_event(
                    session_id=session_id,
                    done=False,
                    stage_id=stage_id,
                    stage_name=stage_name,
                    stage_summary=f"Error in rework stage {stage_id}.",
                    responses=responses_json,
                    final_state="",
                    quality_gates=context.quality_gates,
                )
                return event, state

            responses_json.append(agent_result_to_json(result))
            state["results"].append(agent_result_to_json(result))

        state["rework_stage_index"] = idx + 1

        # If we just finished the last rework stage, decide next.
        if state["rework_stage_index"] >= len(queue):
            mandatory_failed = failed_mandatory_gates(context)
            if mandatory_failed:
                context.artifacts.setdefault(
                    "rework_summary",
                    {"initial_failed_gates": [], "targeted_steps_executed": [], "post_rework_failed_gates": []},
                )
                context.artifacts["rework_summary"]["post_rework_failed_gates"] = mandatory_failed
                state["mode"] = "critic"
                stage_summary = "Rework still failed mandatory gates; awaiting critic (human approval)."
                done = False
                # Pause without executing critic yet.
            else:
                state["mode"] = "done"
                stage_summary = "Rework complete; all mandatory gates passed."
                done = True
        else:
            stage_summary = f"Completed rework stage {stage_id}. Awaiting human review."
            done = False

    elif mode == "critic":
        # Execute critic as a single stage response.
        stage_id = "C"
        stage_name = "Critic Agent"
        stage_summary = "Critic executed."

        for _, fn in handlers["C"]:
            try:
                result = run_response(fn, context)
            except Exception as e:
                err_text = str(e)
                result = AgentResult(
                    status="failed",
                    agent="C",
                    summary=f"Critic stage failed: {err_text[:200]}",
                    findings=[
                        {
                            "id": "C-ERR",
                            "severity": "high",
                            "message": err_text,
                            "action": "Human review required.",
                        }
                    ],
                    artifacts={},
                    next_recommendation="Human_review_required",
                    context_version_out=context.context_version,
                )
                # Pause on critic error
                responses_json.append(agent_result_to_json(result))
                state["results"].append(agent_result_to_json(result))
                state["mode"] = "error"
                state["context"] = context.__dict__
                event = build_stage_event(
                    session_id=session_id,
                    done=False,
                    stage_id="C",
                    stage_name="Critic",
                    stage_summary="Error in critic stage.",
                    responses=responses_json,
                    final_state="",
                    quality_gates=context.quality_gates,
                )
                return event, state

            # Critic doesn't map to quality gate in gate_by_agent; main sets quality_gates["critic"].
            verdict = context.artifacts.get("critic_report", {}).get("verdict", "blocked")
            context.quality_gates["critic"] = verdict
            responses_json.append(agent_result_to_json(result))
            state["results"].append(agent_result_to_json(result))

        state["mode"] = "done"
        done = True

    else:
        # Unknown mode: mark done.
        state["mode"] = "done"
        done = True

    # Persist updated context back into state.
    state["context"] = context.__dict__

    final_state = "REWORK" if any(v == "fail" for v in context.quality_gates.values()) else "DONE"
    if done:
        event = build_stage_event(
            session_id=session_id,
            done=True,
            stage_id=stage_id or "",
            stage_name=stage_name,
            stage_summary=stage_summary,
            responses=responses_json,
            final_state=final_state,
            quality_gates=context.quality_gates,
        )
    else:
        event = build_stage_event(
            session_id=session_id,
            done=False,
            stage_id=stage_id or "",
            stage_name=stage_name,
            stage_summary=stage_summary,
            responses=responses_json,
            final_state="",
            quality_gates=context.quality_gates,
        )
    return event, state


def action_start(args: argparse.Namespace) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    theme_input_path = Path(args.theme_input_path).expanduser()
    theme_input = json.loads(theme_input_path.read_text(encoding="utf-8"))

    context = build_context(theme_input)
    # Tie the context session to the UI session for traceability.
    context.session_id = args.session_id

    context.artifacts["rework_summary"] = {
        "initial_failed_gates": [],
        "targeted_steps_executed": [],
        "post_rework_failed_gates": [],
    }

    state = {
        "session_id": args.session_id,
        "mode": "main",
        "main_stage_index": 0,
        "rework_loop": 0,
        "rework_stage_queue_gates": [],
        "rework_stage_queue": [],
        "rework_stage_index": 0,
        "results": [],
        "context": context.__dict__,
    }

    event, state = execute_one_stage(state, decision="approve")
    save_state(state, Path(args.state_path))
    print(json.dumps(event), flush=True)


def action_step(args: argparse.Namespace) -> None:
    state_path = Path(args.state_path)
    state = load_state(state_path)
    decision = args.decision or "approve"

    event, state = execute_one_stage(state, decision=decision)
    save_state(state, state_path)
    print(json.dumps(event), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ravgentic paused runner (step-by-step UI).")
    parser.add_argument("--action", required=True, choices=["start", "step"])
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--theme-input-path", default="")
    parser.add_argument("--decision", default="approve")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.action == "start":
        action_start(args)
    elif args.action == "step":
        action_step(args)


if __name__ == "__main__":
    main()

