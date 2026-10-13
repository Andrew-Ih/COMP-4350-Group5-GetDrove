import createClient from "openapi-fetch";

import { apiBaseUrl } from "@/shared/config/env";

import type { paths as AccountsPaths } from "./generated/accounts";
import type { paths as NotificationsPaths } from "./generated/notifications";
import type { paths as PaymentsPaths } from "./generated/payments";
import type { paths as RoutingPaths } from "./generated/routing";
import type { paths as TripsPaths } from "./generated/trips";

/**
 * Typed clients for each service, generated from contracts/openapi. Paths, request bodies
 * and responses are checked by TypeScript, so a contract change shows up as a type error.
 *
 *   const { data, error } = await tripsApi.GET("/mine");
 *
 * Use them from client components (they call relative URLs) and from a feature's `api/`
 * folder, not directly from pages. Endpoints under /internal are for services only.
 */
export const accountsApi = createClient<AccountsPaths>({ baseUrl: `${apiBaseUrl}/accounts` });
export const tripsApi = createClient<TripsPaths>({ baseUrl: `${apiBaseUrl}/trips` });
export const routingApi = createClient<RoutingPaths>({ baseUrl: `${apiBaseUrl}/routing` });
export const paymentsApi = createClient<PaymentsPaths>({ baseUrl: `${apiBaseUrl}/payments` });
export const notificationsApi = createClient<NotificationsPaths>({
  baseUrl: `${apiBaseUrl}/notifications`,
});
