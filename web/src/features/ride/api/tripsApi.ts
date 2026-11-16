import { accountsApi, routingApi, tripsApi, unwrap } from "@/shared/api";

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

/**
 * GET /api/trips/{id}?lat&lng&exclude: one trip, with up to 3 pickup points near the rider
 * and the rider's own request on it, if any. Points in `exclude` (ones the rider rejected,
 * #136) are never returned. Without `rider`, the trip comes back with no pickups.
 */
export function getTrip(tripId: string, rider?: { lat: number; lng: number }, exclude: readonly string[] = []) {
  const query = rider && exclude.length > 0 ? { ...rider, exclude: [...exclude] } : rider;
  return unwrap(tripsApi.GET("/{trip_id}", { params: { path: { trip_id: tripId }, query } }));
}

/** GET /api/accounts/users/{id}/profile: the driver's first name, rating and vehicle (no plate). */
export function getProfile(userId: string) {
  return unwrap(accountsApi.GET("/users/{user_id}/profile", { params: { path: { user_id: userId } } }));
}

/** What's sent to ask for a seat: the rider's location, the chosen pickup point and the points they rejected. */
export type SeatRequestBody = { lat: number; lng: number; pickupId: string; exclude?: string[] };

/**
 * POST /api/trips/{id}/requests: asks for a seat, picked up at one of the trip detail's
 * pickup points. The rider's location is sent to check the pickup and is never stored.
 * `exclude` is the same list the trip detail was loaded with, so a point offered after the
 * rider rejected others is still accepted (#299).
 */
export function requestSeat(tripId: string, body: SeatRequestBody) {
  return unwrap(tripsApi.POST("/{trip_id}/requests", { params: { path: { trip_id: tripId } }, body }));
}

/** GET /api/trips/requests/{id}: one request, to see whether the driver has decided. */
export function getSeatRequest(requestId: string) {
  return unwrap(tripsApi.GET("/requests/{request_id}", { params: { path: { request_id: requestId } } }));
}

/** POST /api/trips/requests/{id}/cancel: the rider withdraws a pending or accepted request. */
export function cancelSeatRequest(requestId: string) {
  return unwrap(tripsApi.POST("/requests/{request_id}/cancel", { params: { path: { request_id: requestId } } }));
}
