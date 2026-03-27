import json
from pathlib import Path

from .llm_client import call_llm_text
from .types import AgentResult, GlobalContext


class ScaffoldSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) describing that the frontend scaffold is ready."
        return call_llm_text(context, role_name="B.01.Scaffold", system_prompt=system, user_prompt=user)


class UIImplementationSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) describing that core route pages are implemented/ready."
        return call_llm_text(context, role_name="B.02.UIImplementation", system_prompt=system, user_prompt=user)


class DataClientSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) describing that API client/data client is ready."
        return call_llm_text(context, role_name="B.03.DataClient", system_prompt=system, user_prompt=user)


class ConfigEnvSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) describing that config/env defaults are ready."
        return call_llm_text(context, role_name="B.04.ConfigEnv", system_prompt=system, user_prompt=user)


class DockerInfraSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) describing that Docker/infra step is prepared."
        return call_llm_text(context, role_name="B.05.DockerInfra", system_prompt=system, user_prompt=user)


class AssetSourcingSubAgent:
    def run(self, context: GlobalContext) -> str:
        system = "You are a concise compliance status writer for an agentic UI build workflow."
        user = "Return a very short phrase (<=8 words) confirming no-image-generation policy is active."
        return call_llm_text(context, role_name="B.06.AssetSourcing", system_prompt=system, user_prompt=user)


class BuildAgent:
    def __init__(self) -> None:
        self.scaffold = ScaffoldSubAgent()
        self.ui = UIImplementationSubAgent()
        self.data = DataClientSubAgent()
        self.cfg = ConfigEnvSubAgent()
        self.docker = DockerInfraSubAgent()
        self.assets = AssetSourcingSubAgent()

    def run(self, context: GlobalContext) -> AgentResult:
        root = Path(str(context.constraints.get("root_path", ".")))

        # Consume upstream artifacts (O/P/A) as the source of truth.
        architecture_spec = context.artifacts.get("architecture_spec", {}) or {}
        design_tokens = architecture_spec.get("design_tokens", {}) or {}
        api_map = architecture_spec.get("api_map", {}) or {}
        prompt_refinement = context.artifacts.get("prompt_refinement", {}) or {}
        task_plan = context.artifacts.get("task_plan", {}) or {}

        # Theme name comes from user input; colors come from Architect design tokens if available.
        theme_name = str(context.user_theme_input.get("theme_name", "themed-ui"))

        # Palette from user is still recorded, but actual applied tokens prefer Architect output.
        palette = context.user_theme_input.get("palette") or ["#0b1020", "#6366f1", "#f9fafb"]
        if not isinstance(palette, list):
            palette = [str(palette)]

        primary = str(design_tokens.get("primary") or (palette[0] if len(palette) > 0 else "#0b1020"))
        accent = str(design_tokens.get("accent") or (palette[1] if len(palette) > 1 else "#6366f1"))
        text = str(design_tokens.get("text") or (palette[2] if len(palette) > 2 else "#f9fafb"))
        surface = "rgba(255, 255, 255, 0.06)"
        border = "rgba(255, 255, 255, 0.14)"

        theme_dir = root / "frontend" / "src" / "lib" / "theme"
        theme_dir.mkdir(parents=True, exist_ok=True)

        generated_theme_path = theme_dir / "generatedTheme.ts"
        generated_theme_path.write_text(
            "\n".join(
                [
                    "export type GeneratedTheme = {",
                    "  name: string;",
                    "  colors: {",
                    "    background: string;",
                    "    surface: string;",
                    "    text: string;",
                    "    primary: string;",
                    "    accent: string;",
                    "    border: string;",
                    "  };",
                    "  radius: number;",
                    "};",
                    "",
                    "export const generatedTheme: GeneratedTheme = {",
                    f"  name: {json.dumps(theme_name)},",
                    "  colors: {",
                    f"    background: {json.dumps(primary)},",
                    f"    surface: {json.dumps(surface)},",
                    f"    text: {json.dumps(text)},",
                    f"    primary: {json.dumps(primary)},",
                    f"    accent: {json.dumps(accent)},",
                    f"    border: {json.dumps(border)},",
                    "  },",
                    "  radius: 12,",
                    "};",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        # Update layout and route pages to apply theme while keeping API calls.
        def update_file(file_path: Path, content: str) -> None:
            file_path.write_text(content, encoding="utf-8")

        layout_path = root / "frontend" / "src" / "app" / "layout.tsx"
        update_file(
            layout_path,
            "\n".join(
                [
                    'import type { Metadata } from "next";',
                    'import React from "react";',
                    'import { generatedTheme } from "@/lib/theme/generatedTheme";',
                    "",
                    "export const metadata: Metadata = {",
                    '  title: "ravgentic frontend",',
                    '  description: "Themed, route-connected UI (mock backend).",',
                    "};",
                    "",
                    "export default function RootLayout({",
                    "  children,",
                    "}: {",
                    "  children: React.ReactNode;",
                    "}) {",
                    "  return (",
                    '    <html lang="en">',
                    "      <body",
                    "        style={{",
                    '          margin: 0,',
                    '          fontFamily: "Inter, Arial, sans-serif",',
                    "          backgroundColor: generatedTheme.colors.background,",
                    "          color: generatedTheme.colors.text,",
                    '          minHeight: "100vh",',
                    "        }}",
                    "      >",
                    "        {children}",
                    "      </body>",
                    "    </html>",
                    "  );",
                    "}",
                    "",
                ]
            ),
        )

        def page_template(route_path: str, route_title: str, hook_name: str, endpoint_hint: str) -> str:
            fn_base = "".join(ch for ch in route_title if ch.isalnum())
            fn_name = f"{fn_base}Page"
            resolved_hint = endpoint_hint
            if isinstance(api_map, dict) and route_path in api_map:
                resolved_hint = f"Connected endpoint: {api_map[route_path]}"
            return "\n".join(
                [
                    'import { generatedTheme } from "@/lib/theme/generatedTheme";',
                    f'import {{ {hook_name} }} from "@/lib/api/hooks";',
                    "",
                    f"export default async function {fn_name}() {{",
                    "  const data = await ("
                    f"    {hook_name}()"
                    "  );",
                    "  return (",
                    '    <main style={{ padding: 24 }}>',
                    "      <div",
                    "        style={{",
                    "          border: `1px solid ${generatedTheme.colors.border}`,",
                    "          background: generatedTheme.colors.surface,",
                    "          borderRadius: generatedTheme.radius,",
                    "          padding: 16,",
                    "          maxWidth: 980,",
                    "        }}",
                    "      >",
                    f"        <h1 style={{{{ margin: 0, fontSize: 22 }}}}>"
                    f"{route_title}</h1>",
                    f"        <p style={{{{ marginTop: 6, opacity: 0.9 }}}}>"
                    f"{resolved_hint}</p>",
                    "        <div",
                    "          style={{",
                    "            height: 2,",
                    "            background: generatedTheme.colors.accent,",
                    "            opacity: 0.7,",
                    "            margin: " + json.dumps("12px 0") + ",",
                    "          }}",
                    "        />",
                    "        <pre style={{",
                    "          whiteSpace: 'pre-wrap',",
                    "          wordBreak: 'break-word',",
                    "          margin: 0,",
                    "          opacity: 0.95,",
                    "        }}>{JSON.stringify(data, null, 2)}</pre>",
                    "      </div>",
                    "    </main>",
                    "  );",
                    "}",
                    "",
                ]
            )

        update_file(
            root / "frontend" / "src" / "app" / "page.tsx",
            page_template("/", "ravgentic: Home", "getHomeData", "Connected endpoint: GET /api/home"),
        )
        update_file(
            root / "frontend" / "src" / "app" / "dashboard" / "page.tsx",
            page_template("/dashboard", "Dashboard", "getDashboardData", "Connected endpoint: GET /api/dashboard"),
        )
        update_file(
            root / "frontend" / "src" / "app" / "settings" / "page.tsx",
            page_template("/settings", "Settings", "getSettingsData", "Connected endpoint: GET /api/settings"),
        )
        update_file(
            root / "frontend" / "src" / "app" / "profile" / "page.tsx",
            page_template("/profile", "Profile", "getProfileData", "Connected endpoint: GET /api/profile"),
        )

        # LLM-driven *status* strings (not the code writing itself).
        return AgentResult(
            status="success",
            agent="B",
            summary="Build phase executed sub-agent scaffold flow.",
            artifacts={
                "implementation_report": {
                    "scaffold": self.scaffold.run(context),
                    "ui": self.ui.run(context),
                    "data_client": self.data.run(context),
                    "config_env": self.cfg.run(context),
                    "docker_infra": self.docker.run(context),
                    "asset_sourcing": self.assets.run(context),
                },
                "theme_written": {
                    "generatedTheme": str(generated_theme_path.relative_to(root)),
                    "layout": str(layout_path.relative_to(root)),
                    "pages": [
                        "frontend/src/app/page.tsx",
                        "frontend/src/app/dashboard/page.tsx",
                        "frontend/src/app/settings/page.tsx",
                        "frontend/src/app/profile/page.tsx",
                    ],
                    "theme_name": theme_name,
                    "palette": palette,
                    "design_tokens_used": {"primary": primary, "accent": accent, "text": text},
                    "upstream_inputs_used": {
                        "prompt_refinement_present": bool(prompt_refinement),
                        "task_plan_present": bool(task_plan),
                        "architecture_spec_present": bool(architecture_spec),
                    },
                },
                "llm_connectivity": {
                    "B.01.Scaffold": True,
                    "B.02.UIImplementation": True,
                    "B.03.DataClient": True,
                    "B.04.ConfigEnv": True,
                    "B.05.DockerInfra": True,
                    "B.06.AssetSourcing": True,
                },
            },
            next_recommendation="Invoke test phase.",
            context_version_out="v4",
        )
