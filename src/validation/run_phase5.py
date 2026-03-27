import json
import argparse
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass
class CheckResult:
    name: str
    status: str
    details: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase-5 validation runner")
    parser.add_argument(
        "--artifacts-dir",
        type=str,
        default="artifacts",
        help="Artifacts directory path (absolute or relative to repo root).",
    )
    return parser.parse_args()


def resolve_artifacts_dir(root: Path, artifacts_dir_arg: str) -> Path:
    candidate = Path(artifacts_dir_arg)
    if candidate.is_absolute():
        return candidate
    return root / candidate


def run_command(command: List[str], cwd: Path) -> CheckResult:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            check=True,
            text=True,
            capture_output=True,
        )
        return CheckResult(
            name=" ".join(command),
            status="pass",
            details=(completed.stdout or "").strip()[-1200:],
        )
    except subprocess.CalledProcessError as error:
        return CheckResult(
            name=" ".join(command),
            status="fail",
            details=((error.stdout or "") + "\n" + (error.stderr or "")).strip()[-1200:],
        )


def check_route_files(root: Path) -> CheckResult:
    expected_routes: Dict[str, str] = {
        "/": "frontend/src/app/page.tsx",
        "/dashboard": "frontend/src/app/dashboard/page.tsx",
        "/settings": "frontend/src/app/settings/page.tsx",
        "/profile": "frontend/src/app/profile/page.tsx",
    }
    missing = [path for path in expected_routes.values() if not (root / path).exists()]
    if missing:
        return CheckResult(
            name="route file presence",
            status="fail",
            details="Missing route files: " + ", ".join(missing),
        )
    return CheckResult(
        name="route file presence",
        status="pass",
        details="All core route files are present.",
    )


def check_contract_alignment(root: Path, artifacts_dir: Path) -> CheckResult:
    artifacts_contract = artifacts_dir / "api_contract_map.json"
    frontend_contract_ts = root / "frontend" / "src" / "lib" / "api" / "contracts.ts"
    if not artifacts_contract.exists() or not frontend_contract_ts.exists():
        return CheckResult(
            name="contract alignment",
            status="fail",
            details="Contract file missing in artifacts or frontend scaffold.",
        )

    contract = json.loads(artifacts_contract.read_text(encoding="utf-8"))
    frontend_text = frontend_contract_ts.read_text(encoding="utf-8")

    missing_endpoints = []
    for route_data in contract.values():
        endpoint = route_data["endpoint"]
        if endpoint not in frontend_text:
            missing_endpoints.append(endpoint)

    if missing_endpoints:
        return CheckResult(
            name="contract alignment",
            status="fail",
            details="Missing endpoints in frontend contract: " + ", ".join(missing_endpoints),
        )

    return CheckResult(
        name="contract alignment",
        status="pass",
        details="All artifact endpoints are represented in frontend API contract.",
    )


def parse_contract_endpoints(contract: Dict[str, Dict[str, object]]) -> Dict[str, str]:
    route_to_api_path: Dict[str, str] = {}
    for route, route_data in contract.items():
        raw_endpoint = str(route_data["endpoint"])
        _, endpoint_path = raw_endpoint.split(" ")
        route_to_api_path[route] = endpoint_path
    return route_to_api_path


def wait_for_backend(base_url: str, timeout_seconds: float = 6.0) -> bool:
    started_at = time.time()
    while time.time() - started_at < timeout_seconds:
        try:
            with urllib.request.urlopen(f"{base_url}/api/home", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def check_backend_integration(root: Path, artifacts_dir: Path) -> CheckResult:
    contract_path = artifacts_dir / "api_contract_map.json"
    if not contract_path.exists():
        return CheckResult(
            name="backend integration",
            status="fail",
            details="Missing artifacts/api_contract_map.json.",
        )

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    route_to_api_path = parse_contract_endpoints(contract)
    backend_dir = root / "backend"
    base_url = "http://localhost:4000"
    process = None

    try:
        process = subprocess.Popen(
            ["node", "src/server.js"],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return CheckResult(
            name="backend integration",
            status="fail",
            details="Node.js is not available to start backend server.",
        )

    try:
        if not wait_for_backend(base_url):
            return CheckResult(
                name="backend integration",
                status="fail",
                details="Backend did not become healthy in time.",
            )

        endpoint_failures: List[str] = []
        for route, endpoint_path in route_to_api_path.items():
            expected_schema = contract[route]["response_schema"]
            url = f"{base_url}{endpoint_path}"
            try:
                with urllib.request.urlopen(url, timeout=2.0) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    if response.status != 200:
                        endpoint_failures.append(f"{route} -> status {response.status}")
                        continue
            except urllib.error.URLError as error:
                endpoint_failures.append(f"{route} -> request error: {error}")
                continue

            missing_keys = [
                key for key in expected_schema.keys() if key not in body
            ]
            if missing_keys:
                endpoint_failures.append(
                    f"{route} -> missing response keys: {', '.join(missing_keys)}"
                )

        if endpoint_failures:
            return CheckResult(
                name="backend integration",
                status="fail",
                details=" ; ".join(endpoint_failures),
            )

        return CheckResult(
            name="backend integration",
            status="pass",
            details="All contract endpoints responded with expected keys.",
        )
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def write_reports(artifacts_dir: Path, checks: List[CheckResult]) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    passed = [c for c in checks if c.status == "pass"]
    failed = [c for c in checks if c.status == "fail"]
    overall_status = "pass" if not failed else "fail"

    implementation_report = (
        "# Implementation Report\n\n"
        "## Phase\n"
        "Phase 5 - Validation\n\n"
        "## Current Scope\n"
        "- Frontend scaffold exists.\n"
        "- Shared API client and route contract stubs exist.\n"
        "- Validation command added for reproducible checks.\n\n"
        "## Status\n"
        f"- Overall: `{overall_status}`\n"
        f"- Passed checks: `{len(passed)}`\n"
        f"- Failed checks: `{len(failed)}`\n"
    )

    test_lines = [
        "# Test Report",
        "",
        "## Check Results",
    ]
    for check in checks:
        test_lines.append(f"- `{check.name}` -> `{check.status}`")
        test_lines.append(f"  - {check.details.replace(chr(10), ' ')}")
    test_lines.append("")
    test_lines.append(f"## Overall: `{overall_status}`")

    run_log = {
        "run_id": f"phase5-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "phase": "phase5-validation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": [asdict(c) for c in checks],
        "overall_status": overall_status,
    }

    (artifacts_dir / "implementation_report.md").write_text(
        implementation_report,
        encoding="utf-8",
    )
    (artifacts_dir / "test_report.md").write_text(
        "\n".join(test_lines) + "\n",
        encoding="utf-8",
    )
    (artifacts_dir / "orchestrator_run_log.json").write_text(
        json.dumps(run_log, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    frontend_dir = root / "frontend"
    artifacts_dir = resolve_artifacts_dir(root, args.artifacts_dir)

    checks: List[CheckResult] = []
    checks.append(run_command(["npm", "run", "build"], frontend_dir))
    checks.append(check_route_files(root))
    checks.append(check_contract_alignment(root, artifacts_dir))
    checks.append(check_backend_integration(root, artifacts_dir))

    write_reports(artifacts_dir, checks)

    overall = "PASS" if all(c.status == "pass" for c in checks) else "FAIL"
    print(f"Phase-5 validation finished: {overall}")
    for check in checks:
        print(f"- {check.name}: {check.status}")


if __name__ == "__main__":
    main()
