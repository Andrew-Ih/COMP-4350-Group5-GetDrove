import createClient from "openapi-fetch";

import { apiBaseUrl } from "@/shared/config/env";

import type { paths as AccountsPaths } from "./generated/accounts";
import type { paths as NotificationsPaths } from "./generated/notifications";
import type { paths as PaymentsPaths } from "./generated/payments";
import type { paths as RoutingPaths } from "./generated/routing";
import type { paths as TripsPaths } from "./generated/trips";
import { getAccessToken, refreshSession } from "./session";

/**
 * Typed clients for each service, generated from contracts/openapi. Paths, request bodies
 * and responses are checked by TypeScript, so a contract change shows up as a type error.
 *
 *   const { data, error } = await tripsApi.GET("/mine");
 *
 * Use them from client components (they call relative URLs) and from a feature's `api/`
 * folder, not directly from pages. Endpoints under /internal are for services only.
 */
/**
 * Every API call goes through here:
 * - adds `Authorization: Bearer <token>` once the user has logged in
 * - if the token has expired (401), refreshes the session once and tries again, so the
 *   student doesn't notice. Calls to /auth/* (log in, refresh…) are never retried.
 * - looks up fetch on every request instead of keeping the one that existed at startup,
 *   so the mock API (MSW), which replaces fetch in tests, intercepts these clients too
 */
const fetch = async (request: Request) => {
  const retry = request.clone(); // a request's body can only be sent once
  const token = getAccessToken();
  if (token && !request.headers.has("Authorization")) {
    request.headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await globalThis.fetch(request);
  if (response.status !== 401 || !token || new URL(request.url, "http://local").pathname.includes("/auth/")) {
    return response;
  }
  if (!(await refreshSession())) {
    return response; // couldn't refresh: the 401 stands, and the page asks to log in again
  }
  retry.headers.set("Authorization", `Bearer ${getAccessToken()}`);
  return globalThis.fetch(retry);
};

export const accountsApi = createClient<AccountsPaths>({ baseUrl: `${apiBaseUrl}/accounts`, fetch });
export const tripsApi = createClient<TripsPaths>({ baseUrl: `${apiBaseUrl}/trips`, fetch });
export const routingApi = createClient<RoutingPaths>({ baseUrl: `${apiBaseUrl}/routing`, fetch });
export const paymentsApi = createClient<PaymentsPaths>({ baseUrl: `${apiBaseUrl}/payments`, fetch });
export const notificationsApi = createClient<NotificationsPaths>({
  baseUrl: `${apiBaseUrl}/notifications`,
  fetch,
});
