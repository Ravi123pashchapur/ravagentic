# ravgentic - phased implementation plan

This plan starts small and builds component-by-component. It does not implement everything at once.

## Phase 1 - Foundation (now)

- Create orchestrator entry point that accepts theme input from user.
- Generate initial context and route contract artifact files.
- Keep backend as `mock-backend` mode.
- Enforce policy: no image generation, route-connected elements only.

## Phase 2 - Planner + Architect contracts

- Add `PlannerAgent` to convert theme input to backlog and acceptance criteria.
- Add `ArchitectAgent` to produce:
  - design tokens (color/spacing/typography),
  - route map,
  - frontend-to-backend API contract map.
- Write outputs to:
  - `artifacts/task_plan.md`
  - `artifacts/architecture_spec.md`
  - `artifacts/api_contract_map.json`

## Phase 3 - Build components

- `B.01 Scaffold`: initialize `frontend/` Next.js app.
- `B.02 UI Implementation`: build themed pages:
  - `/`
  - `/dashboard`
  - `/settings`
  - `/profile`
- `B.03 Data Client`: create shared API client and route-level data hooks.
- `B.04 Config/Env`: add `.env.example` for backend URL and model routing vars.

## Phase 4 - Backend connectivity

- In `backend/`, run mock server routes and stable response schemas.
- Ensure each UI route has at least one mapped backend endpoint.
- Add connection checks for happy and error paths.
- Implemented routes:
  - `GET /api/home`
  - `GET /api/dashboard`
  - `GET /api/settings`
  - `GET /api/profile`

## Phase 5 - Validation

- Lint/type/build checks.
- Integration checks: route-to-endpoint mapping.
- Contract checks: schema parity between frontend and mock-backend.
- Output reports:
  - `artifacts/implementation_report.md`
  - `artifacts/test_report.md`
  - `artifacts/orchestrator_run_log.json`
- Command:
  - `python3 src/validation/run_phase5.py`

## Phase 6 - One-command pipeline (new)

- Add orchestrator flag:
  - `python3 src/orchestrator/main.py --auto-validate`
- Behavior:
  - collect theme input,
  - generate planning/architecture artifacts,
  - run Phase-5 validation automatically,
  - print final validation status.

## Component list (individual units)

- `ThemeCollector`
- `ContextEnvelopeBuilder`
- `PlannerAgent`
- `ArchitectAgent`
- `BuildAgent.Scaffold`
- `BuildAgent.UIImplementation`
- `BuildAgent.DataClient`
- `BuildAgent.ConfigEnv`
- `TestAgent.IntegrationCheck`
- `DataContractAgent`

## Note on "mystic-flame" reference

If `mystic-flame` exists as a design reference in `m2r2`, use it as inspiration-only style guidance.
Do not copy code or assets directly.
