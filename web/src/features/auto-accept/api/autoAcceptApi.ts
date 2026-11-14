import { tripsApi, unwrap } from "@/shared/api";

import type { AutoAcceptRules } from "../model/rules";

/** GET /api/trips/auto-accept: the driver's rules. Never set: off, 5 minutes, any rating. */
export function getAutoAcceptRules() {
  return unwrap(tripsApi.GET("/auto-accept"));
}

/** PUT /api/trips/auto-accept: saves the driver's rules. They apply to new requests only. */
export function saveAutoAcceptRules(rules: AutoAcceptRules) {
  return unwrap(tripsApi.PUT("/auto-accept", { body: rules }));
}
