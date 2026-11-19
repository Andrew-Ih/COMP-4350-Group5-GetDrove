"use client";

import { useMutation } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { findPlaces } from "../api/placesApi";
import type { Place } from "../model/places";

/**
 * Looks up a typed address when the user presses Search: a mutation, not a query, so it only
 * runs when asked (no lookup while typing, as Nominatim's usage policy requires) and the
 * address is never kept in the query cache.
 */
export function useFindPlaces() {
  return useMutation<{ places: Place[] }, ApiError, string>({ mutationFn: findPlaces });
}
