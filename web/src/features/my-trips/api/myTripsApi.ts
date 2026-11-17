import { tripsApi, unwrap } from "@/shared/api";

import type { When } from "../model/myTrips";

/** GET /api/trips/mine?when=: the trips this student has posted, cancelled ones included. */
export function getDrivingTrips(when: When) {
  return unwrap(tripsApi.GET("/mine", { params: { query: { when } } }));
}

/** GET /api/trips/requests/mine?when=: the trips this student asked for a seat on, with each request. */
export function getRidingTrips(when: When) {
  return unwrap(tripsApi.GET("/requests/mine", { params: { query: { when } } }));
}

/** POST /api/trips/{id}/cancel: the driver cancels one trip that hasn't started. */
export function cancelTrip(tripId: string) {
  return unwrap(tripsApi.POST("/{trip_id}/cancel", { params: { path: { trip_id: tripId } } }));
}

/** POST /api/trips/series/{id}/cancel: cancels every trip in a recurring series that hasn't started. */
export function cancelSeries(seriesId: string) {
  return unwrap(tripsApi.POST("/series/{series_id}/cancel", { params: { path: { series_id: seriesId } } }));
}
