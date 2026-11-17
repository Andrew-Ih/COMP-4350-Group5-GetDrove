"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type ApiError, retryServerErrors } from "@/shared/api";

import { acceptRequest, declineRequest, getRoute, getTrip, getTripRequests } from "../api/tripsApi";
import type { Trip } from "../model/postTrip";
import { applyDecision, type DriverRequest, type TripDetail } from "../model/requests";

const tripKey = (tripId: string) => ["trips", "detail", tripId] as const;
const requestsKey = (tripId: string) => ["trips", "requests", tripId] as const;

/** The driver's trip: when it leaves, its ends and how many seats are left. */
export function useDriverTrip(tripId: string) {
  return useQuery<TripDetail, ApiError>({
    queryKey: tripKey(tripId),
    queryFn: () => getTrip(tripId),
    retry: retryServerErrors,
  });
}

/** The requests on the driver's trip, with each pickup's detour. */
export function useTripRequests(tripId: string) {
  return useQuery<DriverRequest[], ApiError>({
    queryKey: requestsKey(tripId),
    queryFn: () => getTripRequests(tripId),
    retry: retryServerErrors,
  });
}

/** The trip's full route: the driver sees all of it, including their own start. */
export function useDriverRoute(tripId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["routing", "route", tripId],
    queryFn: () => getRoute(tripId),
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

type Decision = { requestId: string; decision: "accepted" | "declined" };

/**
 * Accepts or declines a request. On success the list and the seat count change straight
 * away, then both are fetched again for the server's pickup order and detours. On failure
 * both are fetched again too, since a 409 means they've changed (e.g. the last seat went).
 */
export function useDecideRequest(tripId: string) {
  const queryClient = useQueryClient();
  return useMutation<unknown, ApiError, Decision>({
    mutationFn: ({ requestId, decision }) => (decision === "accepted" ? acceptRequest(requestId) : declineRequest(requestId)),
    onSuccess: (_, { requestId, decision }) => {
      const detail = queryClient.getQueryData<TripDetail>(tripKey(tripId));
      const requests = queryClient.getQueryData<DriverRequest[]>(requestsKey(tripId));
      if (detail && requests) {
        const next = applyDecision(detail.trip, requests, requestId, decision);
        queryClient.setQueryData<TripDetail>(tripKey(tripId), { ...detail, trip: next.trip });
        queryClient.setQueryData<DriverRequest[]>(requestsKey(tripId), next.requests);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: tripKey(tripId) });
      void queryClient.invalidateQueries({ queryKey: requestsKey(tripId) });
    },
  });
}

/**
 * For the Cancel trip action on the trip page (#273): once cancelled, the page shows the trip
 * as cancelled straight away (so Accept and Decline go), then the trip and its requests are
 * fetched again, since cancelling closes every request. After a failed cancel (e.g. the trip
 * started meanwhile) they're fetched again too.
 */
export function useTripCancelled(tripId: string) {
  const queryClient = useQueryClient();
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: tripKey(tripId) });
    void queryClient.invalidateQueries({ queryKey: requestsKey(tripId) });
  };
  return {
    cancelled: (trips: Trip[]) => {
      const detail = queryClient.getQueryData<TripDetail>(tripKey(tripId));
      const trip = trips.find((t) => t.id === tripId);
      if (detail && trip) queryClient.setQueryData<TripDetail>(tripKey(tripId), { ...detail, trip });
      refresh();
    },
    failed: refresh,
  };
}
