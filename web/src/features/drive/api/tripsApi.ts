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
