import { getJson } from "./client";
import { ENDPOINTS } from "./endpoints";

export async function getHomeData() {
  return getJson<Record<string, unknown>>(ENDPOINTS.home);
}

export async function getDashboardData() {
  return getJson<Record<string, unknown>>(ENDPOINTS.dashboard);
}

export async function getSettingsData() {
  return getJson<Record<string, unknown>>(ENDPOINTS.settings);
}

export async function getProfileData() {
  return getJson<Record<string, unknown>>(ENDPOINTS.profile);
}
