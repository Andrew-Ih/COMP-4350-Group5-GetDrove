"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { cancelSeries, cancelTrip, getDrivingTrips, getRidingTrips } from "../api/myTripsApi";
import { markCancelled, type RiderTrip, type Trip, type When } from "../model/myTrips";

const drivingKey = (when: When) => ["trips", "mine", "driver", when] as const;
const ridingKey = (when: When) => ["trips", "mine", "rider", when] as const;

export function useDrivingTrips(when: When, enabled = true) {
  return useQuery<Trip[], ApiError>({ queryKey: drivingKey(when), queryFn: () => getDrivingTrips(when), enabled });
}

export function useRidingTrips(when: When, enabled = true) {
  return useQuery<RiderTrip[], ApiError>({ queryKey: ridingKey(when), queryFn: () => getRidingTrips(when), enabled });
}

/** One trip, or every trip in its series that hasn't started. */
export type CancelChoice = { trip: Trip; scope: "trip" | "series" };

/**
 * Cancels a trip or its series. The cancelled trips show as cancelled straight away, then
 * the lists are fetched again (a 409 means the trip changed, e.g. it already started).
 */
export function useCancelTrip() {
  const queryClient = useQueryClient();
  return useMutation<Trip[], ApiError, CancelChoice>({
    mutationFn: async ({ trip, scope }) =>
      scope === "series" && trip.seriesId ? cancelSeries(trip.seriesId) : [await cancelTrip(trip.id)],
    onSuccess: (cancelled) => {
      queryClient.setQueryData<Trip[]>(drivingKey("upcoming"), (trips) => trips && markCancelled(trips, cancelled));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["trips", "mine", "driver"] }),
  });
}
