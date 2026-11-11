"use client";

import { useQuery } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getProfile, getRoute, getTrip } from "../api/tripsApi";
import type { RouteFeature } from "../model/results";
import type { DriverProfile, TripDetail } from "../model/tripDetail";

/** One trip with the pickup points near `rider`. Refetched when the rider comes back to it. */
export function useTripDetail(tripId: string, rider: { lat: number; lng: number } | undefined) {
  return useQuery<TripDetail, ApiError>({
    queryKey: ["trips", "detail", tripId, rider?.lat, rider?.lng],
    queryFn: () => getTrip(tripId, rider),
  });
}

/** The driver's public profile. Optional on the screen: the trip still shows without it. */
export function useProfile(userId: string | undefined) {
  return useQuery<DriverProfile, ApiError>({
    queryKey: ["accounts", "profile", userId],
    queryFn: () => getProfile(userId!),
    enabled: Boolean(userId),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/**
 * A trip's route, shared with the results map's cache (same key), so it isn't fetched twice.
 * `enabled` waits for the trip itself, so a trip that's gone doesn't ask for its route.
 */
export function useRoute(tripId: string, enabled: boolean) {
  return useQuery<RouteFeature, ApiError>({
    queryKey: ["routing", "route", tripId],
    queryFn: () => getRoute(tripId),
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}
