import { routingApi, tripsApi, unwrap } from "@/shared/api";

import type { SearchQuery } from "../model/search";

/**
 * GET /api/trips/search: trips whose route passes within walking distance of the rider,
 * soonest first, each with a pickup point and the rider's estimated share.
 */
export function searchTrips(query: SearchQuery) {
  return unwrap(tripsApi.GET("/search", { params: { query } }));
}

/** GET /api/routing/trips/{id}/geometry: the trip's route as a GeoJSON line, for the map. */
export function getRoute(tripId: string) {
  return unwrap(routingApi.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: tripId } } }));
}
