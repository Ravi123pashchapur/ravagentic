let sessionId = null;
let stages = [];
let lastStage = null;

const startBtn = document.getElementById("startBtn");
const approveBtn = document.getElementById("approveBtn");
const stopBtn = document.getElementById("stopBtn");
const statusLine = document.getElementById("statusLine");
const reviewHint = document.getElementById("reviewHint");
const timelineEl = document.getElementById("timeline");
const logBox = document.getElementById("logBox");

function setExecuting(isExecuting, label) {
  const labelText = label ? ` - ${label}` : "";
  statusLine.innerHTML = isExecuting ? `<span class="spinner" style="display:inline-block;vertical-align:middle;margin-right:8px;"></span>Running${labelText}` : "";
}

function escapeHtml(s) {
  return (s || "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTimeline() {
  timelineEl.innerHTML = "";
  stages.forEach((s, idx) => {
    const div = document.createElement("div");
    div.className = "step" + (idx === stages.length - 1 ? " active" : "") + " " + (idx < stages.length - 1 ? "done" : "");
    const left = document.createElement("div");
    left.className = "left";

    const badge = document.createElement("div");
    badge.className = "badge";
    badge.textContent = s.stage_id || s.id || s.agent_id || "?";

    const meta = document.createElement("div");
    const title = document.createElement("div");
    title.style.fontWeight = "700";
    title.textContent = `${s.stage_id || s.id}`;

    const sub = document.createElement("div");
    sub.style.fontSize = "12px";
    sub.style.opacity = "0.85";
    sub.textContent = s.stage_name || s.summary || "Completed";

    meta.appendChild(title);
    meta.appendChild(sub);
    left.appendChild(badge);
    left.appendChild(meta);

    const right = document.createElement("div");
    right.style.fontSize = "12px";
    right.style.opacity = "0.85";
    right.textContent = s.awaiting_review ? "Waiting review" : "Ready";

    div.appendChild(left);
    div.appendChild(right);
    timelineEl.appendChild(div);
  });
}

function renderFindings(findings) {
  if (!findings || !findings.length) return "<div class='hint'>No findings.</div>";
  const rows = findings
    .map((f) => {
      const id = escapeHtml(f.id);
      const sev = escapeHtml(f.severity);
      const msg = escapeHtml(f.message);
      const action = escapeHtml(f.action);
      return `<div class="kv"><strong>${id}</strong> [${sev}] - ${msg}${action ? `<br/>Action: ${action}` : ""}</div>`;
    })
    .join("");
  return rows;
}

function renderKnownArtifacts(agent, artifacts) {
  if (!artifacts || typeof artifacts !== "object") return "<div class='hint'>No artifacts returned.</div>";

  function section(title, innerHtml) {
    return `<div class="subSection"><div class="subTitle">${escapeHtml(title)}</div>${innerHtml}</div>`;
  }

  const out = [];

  if (artifacts.llm_connectivity) {
    out.push(
      section(
        "LLM Connectivity (sub-agents)",
        `<div class="kv">${escapeHtml(JSON.stringify(artifacts.llm_connectivity, null, 2))}</div>`
      )
    );
  }

  // Orchestrator prompt refinement
  if (artifacts.prompt_refinement) {
    const pr = artifacts.prompt_refinement;
    out.push(
      section(
        "O Sub-agent: PromptRefiner",
        `<div class="kv">refinement_mode: ${escapeHtml(pr.refinement_mode)}<br/>raw_prompt: ${escapeHtml(
          pr.raw_prompt
        )}<br/>refined_prompt: ${escapeHtml(pr.refined_prompt)}</div>`
      )
    );
  }

  // Planner
  if (artifacts.task_plan) {
    const tp = artifacts.task_plan || {};
    const theme = tp.parsed_requirements ? tp.parsed_requirements.theme : "";
    const tasks = tp.tasks || [];
    const risks = tp.risks || [];
    out.push(
      section(
        "P Sub-agent: TaskPlan",
        `<div class="kv">theme: ${escapeHtml(theme)}<br/>tasks: ${escapeHtml(tasks.join(", "))}<br/>risks: ${escapeHtml(
          risks.join(", ")
        )}</div>`
      )
    );
  }
  if (artifacts.acceptance_criteria) {
    out.push(
      section(
        "P Sub-agent: AcceptanceCriteria",
        `<div class="kv">${escapeHtml((artifacts.acceptance_criteria || []).join("\n"))}</div>`
      )
    );
  }

  // Architect
  if (artifacts.architecture_spec) {
    const a = artifacts.architecture_spec || {};
    const tokens = a.design_tokens || {};
    const apiMap = a.api_map || {};
    const templates = a.templates || [];
    const folders = a.folders || [];
    out.push(
      section(
        "A Sub-agent: ArchitectureSpec",
        `<div class="kv">templates: ${escapeHtml(templates.join(", "))}<br/>folders: ${escapeHtml(
          folders.join(", ")
        )}<br/>tokens: ${escapeHtml(JSON.stringify(tokens, null, 2))}<br/>api_map: ${escapeHtml(
          JSON.stringify(apiMap, null, 2)
        )}</div>`
      )
    );
  }

  // Build
  if (artifacts.implementation_report) {
    const b = artifacts.implementation_report || {};
    out.push(
      section(
        "B Sub-agents: ImplementationReport",
        `<div class="kv">${escapeHtml(JSON.stringify(b, null, 2))}</div>`
      )
    );
  }

  // Test
  if (artifacts.test_report) {
    out.push(section("T Sub-agents: TestReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.test_report, null, 2))}</div>`));
  }

  // Security
  if (artifacts.security_report) {
    out.push(section("S Sub-agents: SecurityReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.security_report, null, 2))}</div>`));
  }

  // Performance
  if (artifacts.performance_report) {
    out.push(section("F Sub-agents: PerformanceReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.performance_report, null, 2))}</div>`));
  }

  // Contract
  if (artifacts.contract_report) {
    out.push(section("D Sub-agents: ContractReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.contract_report, null, 2))}</div>`));
  }

  // Release
  if (artifacts.release_report) {
    out.push(section("R Sub-agents: ReleaseReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.release_report, null, 2))}</div>`));
  }

  // Observability
  if (artifacts.observability_report) {
    out.push(section("V Sub-agents: ObservabilityReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.observability_report, null, 2))}</div>`));
  }

  // Critic (conditional)
  if (artifacts.critic_report) {
    out.push(section("C Sub-agents: CriticReport", `<div class="kv">${escapeHtml(JSON.stringify(artifacts.critic_report, null, 2))}</div>`));
  }

  // Fallback: show raw artifacts
  if (out.length === 0) {
    out.push(section("Artifacts (raw)", `<div class="kv">${escapeHtml(JSON.stringify(artifacts, null, 2))}</div>`));
  }

  return out.join("");
}

function renderEvent(event) {
  const awaitingReview = !event.done;

  const stage = event.stage || {};
  stages.push({
    stage_id: stage.stage_id || stage.id || "",
    stage_name: stage.stage_name || "",
    summary: stage.summary || "",
    awaiting_review: awaitingReview,
  });

  lastStage = stage;
  renderTimeline();

  if (event.done) {
    reviewHint.textContent = `Workflow finished: ${event.final_state || "DONE"}`;
    approveBtn.disabled = true;
    stopBtn.disabled = true;
  } else {
    reviewHint.textContent = "Review the agent response. Approve to run the next step.";
    approveBtn.disabled = false;
    stopBtn.disabled = false;
  }

  // Render logs
  const responses = stage.responses || [];
  if (!responses.length) {
    logBox.textContent = "No responses returned for this stage.";
    return;
  }

  // Put a text log first for quick copy, plus a richer artifact HTML below.
  const raw = JSON.stringify({ stage_id: stage.stage_id, responses }, null, 2);
  logBox.textContent = raw;

  // Also render a lightweight HTML summary right under logBox.
  // (We avoid mixing HTML/JSON too much; minimal requirement.)
  const rich = responses
    .map((r) => {
      const agent = r.agent;
      const artifactsHtml = renderKnownArtifacts(agent, r.artifacts);
      return `<div class="subSection"><div class="subTitle">${escapeHtml(agent)} response</div>${artifactsHtml}${renderFindings(r.findings)}</div>`;
    })
    .join("");

  // Insert rich HTML after logBox (without overwriting the log JSON content)
  const existing = document.getElementById("richArtifacts");
  if (existing) existing.remove();
  const richEl = document.createElement("div");
  richEl.id = "richArtifacts";
  richEl.innerHTML = rich;
  logBox.parentElement.appendChild(richEl);
}

async function startWorkflow() {
  const uiPrompt = document.getElementById("ui_prompt").value.trim();
  const themeName = document.getElementById("theme_name").value.trim();
  const referenceTemplatePath = document.getElementById("reference_template_path").value.trim();
  const styleKeywordsRaw = document.getElementById("style_keywords").value.trim();
  const paletteRaw = document.getElementById("palette").value.trim();

  if (!uiPrompt) {
    alert("ui_prompt is required");
    return;
  }

  setExecuting(true, "starting workflow");
  approveBtn.disabled = true;
  stopBtn.disabled = true;
  timelineEl.innerHTML = "";
  stages = [];
  logBox.textContent = "";
  reviewHint.textContent = "";
  document.getElementById("richArtifacts")?.remove();

  const payload = {
    ui_prompt: uiPrompt,
    theme_name: themeName || "modern-dark",
    reference_template_path: referenceTemplatePath || "",
  };
  if (styleKeywordsRaw) payload.style_keywords = styleKeywordsRaw.split(",").map((s) => s.trim()).filter(Boolean);
  if (paletteRaw) payload.palette = paletteRaw.split(",").map((s) => s.trim()).filter(Boolean);

  const resp = await fetch("/api/run/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  sessionId = data.session_id;
  setExecuting(false);
  renderEvent(data.event);
}

async function nextWorkflow() {
  if (!sessionId) return;
  setExecuting(true, "running next agent stage");
  approveBtn.disabled = true;
  stopBtn.disabled = true;

  const resp = await fetch("/api/run/next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, decision: "approve" }),
  });
  const data = await resp.json();
  setExecuting(false);
  renderEvent(data.event);
}

async function stopWorkflow() {
  if (!sessionId) return;
  setExecuting(true, "stopping");

  const resp = await fetch("/api/run/next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, decision: "stop" }),
  });
  const data = await resp.json();
  sessionId = null;
  setExecuting(false);
  reviewHint.textContent = "Workflow stopped by human.";
  approveBtn.disabled = true;
  stopBtn.disabled = true;
}

startBtn.addEventListener("click", startWorkflow);
approveBtn.addEventListener("click", nextWorkflow);
stopBtn.addEventListener("click", stopWorkflow);

