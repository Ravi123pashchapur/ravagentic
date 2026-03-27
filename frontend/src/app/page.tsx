import { generatedTheme } from "@/lib/theme/generatedTheme";
import { getHomeData } from "@/lib/api/hooks";

export default async function ravgenticHomePage() {
  const data = await (    getHomeData()  );
  return (
    <main style={{ padding: 24 }}>
      <div
        style={{
          border: `1px solid ${generatedTheme.colors.border}`,
          background: generatedTheme.colors.surface,
          borderRadius: generatedTheme.radius,
          padding: 16,
          maxWidth: 980,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22 }}>ravgentic: Home</h1>
        <p style={{ marginTop: 6, opacity: 0.9 }}>Connected endpoint: GET /api/home</p>
        <div
          style={{
            height: 2,
            background: generatedTheme.colors.accent,
            opacity: 0.7,
            margin: "12px 0",
          }}
        />
        <pre style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          margin: 0,
          opacity: 0.95,
        }}>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </main>
  );
}
