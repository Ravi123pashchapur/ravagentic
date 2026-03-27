const http = require("http");

const port = process.env.PORT ? Number(process.env.PORT) : 4000;

const responses = {
  "/api/home": {
    headline: "Welcome to ravgentic",
    highlights: ["theme-driven", "route-connected", "mock backend"]
  },
  "/api/dashboard": {
    stats: [{ key: "users", value: 128 }, { key: "errors", value: 2 }],
    notifications: [{ id: "n1", message: "Build healthy" }]
  },
  "/api/settings": {
    preferences: { mode: "dark", density: "comfortable" },
    flags: { betaPanel: true }
  },
  "/api/profile": {
    user: { id: "u_1", name: "Ravgentic User" },
    activity: [{ type: "login", at: "2026-03-26T10:00:00Z" }]
  }
};

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

const server = http.createServer((req, res) => {
  if (req.method !== "GET") {
    sendJson(res, 405, { message: "Method not allowed", code: "METHOD_NOT_ALLOWED" });
    return;
  }

  const url = req.url || "/";
  const payload = responses[url];
  if (!payload) {
    sendJson(res, 404, { message: "Not found", code: "NOT_FOUND" });
    return;
  }

  sendJson(res, 200, payload);
});

server.listen(port, () => {
  console.log(`Mock backend listening on http://localhost:${port}`);
});
