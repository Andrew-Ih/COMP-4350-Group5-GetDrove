import { apiBaseUrl } from "@/shared/config/env";

import type { ServiceName } from "../model/services";

/** Calls GET /api/<service>/health through the gateway. Never throws. */
export async function checkHealth(
  service: ServiceName,
  fetchImpl: typeof fetch = fetch,
): Promise<"up" | "down"> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/${service}/health`, { cache: "no-store" });
    if (!response.ok) {
      return "down";
    }
    const body = (await response.json()) as { status?: string };
    return body.status === "ok" ? "up" : "down";
  } catch {
    return "down";
  }
}
