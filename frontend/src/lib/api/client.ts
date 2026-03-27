const DEFAULT_BACKEND_BASE_URL = "http://localhost:4000";

function backendBaseUrl(): string {
  return process.env.NEXT_PUBLIC_BACKEND_BASE_URL ?? DEFAULT_BACKEND_BASE_URL;
}

export async function getJson<T>(endpointPath: string): Promise<T> {
  const response = await fetch(`${backendBaseUrl()}${endpointPath}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const fallbackMessage = `Request failed with status ${response.status}`;
    throw new Error(fallbackMessage);
  }

  return (await response.json()) as T;
}
