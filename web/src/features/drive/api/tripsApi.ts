import { routingApi, tripsApi, unwrap } from "@/shared/api";

import type { PostTripRequest } from "../model/postTrip";

/**
 * POST /api/trips/: posts a one-off trip. The route is worked out when it's posted, so
 * the response already has the duration, distance and estimated arrival.
 */
export function postTrip(body: PostTripRequest) {
  return unwrap(tripsApi.POST("/", { body }));
}

/** GET /api/trips/mine?role=driver: the trips this student has posted that haven't happened yet. */
export function getMyDrivingTrips() {
  return unwrap(tripsApi.GET("/mine", { params: { query: { role: "driver" } } }));
}

/** GET /api/routing/trips/{id}/geometry: the trip's route, for the map. Drivers get all of it. */
export function getRoute(tripId: string) {
  return unwrap(routingApi.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: tripId } } }));
}

/** GET /api/trips/{id}: one trip. The driver gets their own end of it back too. */
export function getTrip(tripId: string) {
  return unwrap(tripsApi.GET("/{trip_id}", { params: { path: { trip_id: tripId } } }));
}

/** GET /api/trips/{id}/requests: pending requests first, then accepted ones, each with its detour. */
export function getTripRequests(tripId: string) {
  return unwrap(tripsApi.GET("/{trip_id}/requests", { params: { path: { trip_id: tripId } } }));
}

/** POST /api/trips/requests/{id}/accept: gives the rider a seat. 409 `seat_taken` if none is left. */
export function acceptRequest(requestId: string) {
  return unwrap(tripsApi.POST("/requests/{request_id}/accept", { params: { path: { request_id: requestId } } }));
}

/** POST /api/trips/requests/{id}/decline: turns down a pending request. */
export function declineRequest(requestId: string) {
  return unwrap(tripsApi.POST("/requests/{request_id}/decline", { params: { path: { request_id: requestId } } }));
}
