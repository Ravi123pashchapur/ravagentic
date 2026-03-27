const http = require("http");
const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");
const url = require("url");
const { execFile } = require("child_process");

const repoRoot = path.resolve(__dirname, "..");
const publicDir = path.join(__dirname, "public");
const sessionsDir = path.join(__dirname, ".sessions");
const venvPython = path.join(repoRoot, ".venv", "bin", "python3");

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

ensureDir(sessionsDir);

function jsonResponse(res, statusCode, body) {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

function getContentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".map":
      return "application/json; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk.toString("utf8");
    });
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

async function callPythonRunner(args, cwd) {
  return new Promise((resolve, reject) => {
    execFile(venvPython, args, { cwd, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        const message = stderr ? stderr.toString().trim() : err.message;
        return reject(new Error(message));
      }
      try {
        resolve(JSON.parse(stdout.toString()));
      } catch (e) {
        reject(new Error(`Failed to parse python output: ${stdout.toString().slice(0, 500)}`));
      }
    });
  });
}

function safeJoin(base, requested) {
  const decoded = decodeURIComponent(requested || "");
  const joined = path.join(base, decoded);
  const normalized = path.normalize(joined);
  if (!normalized.startsWith(base)) return null;
  return normalized;
}

const server = http.createServer(async (req, res) => {
  try {
    const parsed = url.parse(req.url, true);
    const pathname = parsed.pathname || "/";

    // API routes
    if (req.method === "POST" && pathname === "/api/run/start") {
      const body = await readBody(req);

      const uiPrompt = (body.ui_prompt || "").toString();
      const themeName = (body.theme_name || "modern-dark").toString();
      const styleKeywords = Array.isArray(body.style_keywords)
        ? body.style_keywords
        : (body.style_keywords || "").toString().split(",").map((s) => s.trim()).filter(Boolean);
      const palette = Array.isArray(body.palette)
        ? body.palette
        : (body.palette || "").toString().split(",").map((s) => s.trim()).filter(Boolean);
      const referenceTemplatePath = (body.reference_template_path || "").toString();

      if (!uiPrompt) {
        return jsonResponse(res, 400, { error: "ui_prompt is required" });
      }

      const sessionId = `ui-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const sessionDir = path.join(sessionsDir, sessionId);
      ensureDir(sessionDir);

      const themeInput = {
        ui_prompt: uiPrompt,
        theme_name: themeName,
        style_keywords: styleKeywords.length ? styleKeywords : ["minimal", "clean", "responsive"],
        palette: palette.length ? palette : ["#111827", "#6366f1", "#f9fafb"],
      };
      if (referenceTemplatePath) {
        themeInput.reference_template_path = referenceTemplatePath;
      }

      const themePath = path.join(sessionDir, "theme_input.json");
      const statePath = path.join(sessionDir, "state.json");
      await fsp.writeFile(themePath, JSON.stringify(themeInput, null, 2), "utf8");

      const pyPath = path.join(repoRoot, "src", "orchestrator", "paused_runner.py");
      const output = await callPythonRunner(
        [
          pyPath,
          "--action",
          "start",
          "--session-id",
          sessionId,
          "--state-path",
          statePath,
          "--theme-input-path",
          themePath,
        ],
        repoRoot
      );

      return jsonResponse(res, 200, { session_id: sessionId, event: output });
    }

    if (req.method === "POST" && pathname === "/api/run/next") {
      const body = await readBody(req);
      const sessionId = (body.session_id || "").toString();
      const decision = (body.decision || "approve").toString().toLowerCase();

      if (!sessionId) return jsonResponse(res, 400, { error: "session_id is required" });
      const sessionDir = path.join(sessionsDir, sessionId);
      const statePath = path.join(sessionDir, "state.json");

      if (decision === "stop") {
        // Best-effort cleanup (do not error if missing).
        fs.rmSync(sessionDir, { recursive: true, force: true });
        return jsonResponse(res, 200, { done: true, stopped: true, session_id: sessionId });
      }

      const pyPath = path.join(repoRoot, "src", "orchestrator", "paused_runner.py");
      const output = await callPythonRunner(
        [pyPath, "--action", "step", "--session-id", sessionId, "--state-path", statePath, "--decision", decision],
        repoRoot
      );
      return jsonResponse(res, 200, { session_id: sessionId, event: output });
    }

    // Static file serving
    let filePath;
    if (pathname === "/") {
      filePath = path.join(publicDir, "index.html");
    } else {
      filePath = safeJoin(publicDir, pathname.replace(/^\//, ""));
    }

    if (!filePath) return jsonResponse(res, 400, { error: "Invalid path" });
    if (!fs.existsSync(filePath)) return jsonResponse(res, 404, { error: "Not found" });

    const contentType = getContentType(filePath);
    const content = await fsp.readFile(filePath);
    res.writeHead(200, { "Content-Type": contentType, "Content-Length": content.length });
    res.end(content);
  } catch (err) {
    jsonResponse(res, 500, { error: err.message || String(err) });
  }
});

const port = process.env.PORT ? Number(process.env.PORT) : 4001;
server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`ravgentic-ui listening on http://localhost:${port}`);
  // eslint-disable-next-line no-console
  console.log(`Open http://localhost:${port}/ in your browser`);
});

