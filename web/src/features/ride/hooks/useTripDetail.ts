"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { cancelSeatRequest, getProfile, getRoute, getSeatRequest, getTrip, requestSeat, type SeatRequestBody } from "../api/tripsApi";
import type { RouteFeature } from "../model/results";
import { type DriverProfile, REQUEST_POLL_MS, type SeatRequest, type TripDetail } from "../model/tripDetail";

/**
 * One trip with the pickup points near `rider`, leaving out the ones in `exclude` (#136).
 * Refetched when the rider comes back to it. While other points are being found, the
 * previous answer stays on screen (`isPlaceholderData`) instead of a blank loading state.
 */
export function useTripDetail(tripId: string, rider: { lat: number; lng: number } | undefined, exclude: readonly string[] = []) {
  return useQuery<TripDetail, ApiError>({
    queryKey: ["trips", "detail", tripId, rider?.lat, rider?.lng, [...exclude]],
    queryFn: () => getTrip(tripId, rider, exclude),
    placeholderData: keepPreviousData,
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

const requestKey = (requestId: string | undefined) => ["trips", "request", requestId] as const;

/**
 * The rider's request on this trip, asked for again every few seconds while it's pending,
 * so the screen changes when the driver accepts or declines. `initial` is the request the
 * trip detail already sent, so nothing is fetched until it's time to check again.
 */
export function useSeatRequest(requestId: string | undefined, initial: SeatRequest | undefined) {
  return useQuery<SeatRequest, ApiError>({
    queryKey: requestKey(requestId),
    queryFn: () => getSeatRequest(requestId!),
    enabled: Boolean(requestId),
    initialData: initial && initial.id === requestId ? initial : undefined,
    staleTime: REQUEST_POLL_MS,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? REQUEST_POLL_MS : false),
    retry: false,
  });
}

/**
 * Sends a request for a seat. Afterwards (success or not) the trip is fetched again: seats
 * left, the rider's request, or new pickup points if the chosen one went away.
 */
export function useRequestSeat(tripId: string, onSent: (request: SeatRequest) => void) {
  const queryClient = useQueryClient();
  return useMutation<SeatRequest, ApiError, SeatRequestBody>({
    mutationFn: (body) => requestSeat(tripId, body),
    onSuccess: (request) => {
      queryClient.setQueryData(requestKey(request.id), request);
      onSent(request);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["trips", "detail", tripId] }),
  });
}

/** Cancels the rider's request, then fetches the trip again (its seat may be free now). */
export function useCancelSeatRequest(tripId: string) {
  const queryClient = useQueryClient();
  return useMutation<SeatRequest, ApiError, string>({
    mutationFn: cancelSeatRequest,
    // A check that's still on its way would otherwise put "pending" back over "cancelled".
    onMutate: (requestId) => queryClient.cancelQueries({ queryKey: requestKey(requestId) }),
    onSuccess: (request) => queryClient.setQueryData(requestKey(request.id), request),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["trips", "detail", tripId] }),
  });
}
