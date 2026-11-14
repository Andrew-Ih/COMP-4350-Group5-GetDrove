import { ApiError } from "./problem";

/**
 * Whether a failed query is tried again: once, and only when the problem might go away by
 * itself, that is a server error (5xx, e.g. `routing_unavailable` while routing is slow)
 * or the request not getting through at all. Never for a 4xx: a missing trip or an ended
 * session won't change by asking again, and retrying only delays the message (#39).
 */
export function retryServerErrors(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  return !(error instanceof ApiError) || error.status >= 500;
}
