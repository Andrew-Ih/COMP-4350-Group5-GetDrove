import { routingApi, unwrap } from "@/shared/api";

/**
 * POST /api/routing/places (#257): the places in Winnipeg matching a typed address, best
 * first; an empty list when nothing matches. A POST, so the address is never in a URL.
 */
export function findPlaces(query: string) {
  return unwrap(routingApi.POST("/places", { body: { query } }));
}
