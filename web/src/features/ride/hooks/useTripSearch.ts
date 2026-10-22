"use client";

import { useQueries, useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useCallback } from "react";

import type { ApiError } from "@/shared/api";

import { getRoute, searchTrips } from "../api/tripsApi";
import type { RouteFeature, SearchResult } from "../model/results";
import type { SearchQuery } from "../model/search";

/** The results for one search. Kept for a minute, so going back and forth doesn't search again. */
export function useTripSearch(query: SearchQuery | undefined) {
  return useQuery<SearchResult[], ApiError>({
    queryKey: ["trips", "search", query],
    queryFn: () => searchTrips(query!),
    enabled: Boolean(query),
    staleTime: 60_000,
  });
}

/**
 * The routes of the trips in the results, for the map: trip id → route, for the ones that
 * have loaded. A trip's route doesn't change, so each is fetched once. A missing route
 * (404) is left out; the list still works without it.
 */
export function useRoutes(tripIds: string[]): Map<string, RouteFeature> {
  // A stable function, so TanStack Query only builds a new Map when a route arrives.
  const combine = useCallback(
    (results: UseQueryResult<RouteFeature>[]) => {
      const routes = new Map<string, RouteFeature>();
      results.forEach((result, i) => {
        if (result.data) routes.set(tripIds[i]!, result.data);
      });
      return routes;
    },
    [tripIds],
  );
  return useQueries({
    queries: tripIds.map((tripId) => ({
      queryKey: ["routing", "route", tripId],
      queryFn: () => getRoute(tripId),
      staleTime: Number.POSITIVE_INFINITY,
      retry: false,
    })),
    combine,
  });
}
