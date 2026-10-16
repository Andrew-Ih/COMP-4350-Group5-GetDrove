"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getMyDrivingTrips, getRoute, postTrip } from "../api/tripsApi";
import type { PostTripRequest, Trip } from "../model/postTrip";

const MY_DRIVING_TRIPS = ["trips", "mine", "driver"] as const;

export function usePostTrip() {
  const queryClient = useQueryClient();
  return useMutation<Trip, ApiError, PostTripRequest>({
    mutationFn: postTrip,
    // The new trip is one of "my trips" now.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MY_DRIVING_TRIPS }),
  });
}

/**
 * Reads the driver's upcoming trips fresh, just before posting, to warn about a clash.
 * Undefined if they can't be loaded: the warning is a convenience, so posting goes ahead.
 */
export function useMyDrivingTrips() {
  const queryClient = useQueryClient();
  return () =>
    queryClient
      .fetchQuery({ queryKey: MY_DRIVING_TRIPS, queryFn: getMyDrivingTrips, staleTime: 0 })
      .catch(() => undefined);
}

/** A posted trip's route, for the map. A missing route (404) is left off; the trip is still posted. */
export function useTripRoute(tripId: string | undefined) {
  return useQuery({
    queryKey: ["routing", "route", tripId],
    queryFn: () => getRoute(tripId!),
    enabled: Boolean(tripId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}
