import { API_CONTRACT_MAP, RoutePath } from "./contracts";

function endpointFromContract(routePath: RoutePath): string {
  const contractEntry = API_CONTRACT_MAP[routePath].endpoint;
  const [method, endpointPath] = contractEntry.split(" ");
  if (method !== "GET") {
    throw new Error(`Only GET endpoints are scaffolded in Phase-3. Found: ${method}`);
  }
  return endpointPath;
}

export const ENDPOINTS = {
  home: endpointFromContract("/"),
  dashboard: endpointFromContract("/dashboard"),
  settings: endpointFromContract("/settings"),
  profile: endpointFromContract("/profile")
} as const;
