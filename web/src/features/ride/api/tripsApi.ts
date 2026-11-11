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
 * GET /api/trips/{id}?lat&lng: one trip, with up to 3 pickup points near the rider and the
 * rider's own request on it, if any. Without `rider`, the trip comes back with no pickups.
 */
export function getTrip(tripId: string, rider?: { lat: number; lng: number }) {
  return unwrap(tripsApi.GET("/{trip_id}", { params: { path: { trip_id: tripId }, query: rider } }));
}

/** GET /api/accounts/users/{id}/profile: the driver's first name, rating and vehicle (no plate). */
export function getProfile(userId: string) {
  return unwrap(accountsApi.GET("/users/{user_id}/profile", { params: { path: { user_id: userId } } }));
}

/**
 * POST /api/trips/{id}/requests: asks for a seat, picked up at one of the trip detail's
 * pickup points. The rider's location is sent to check the pickup and is never stored.
 */
export function requestSeat(tripId: string, body: { lat: number; lng: number; pickupId: string }) {
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
