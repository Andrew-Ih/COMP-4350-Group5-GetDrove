"use client";

import { useMutation } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { findPlaces } from "../api/placesApi";
import type { Place } from "../model/places";

/**
 * Looks up a typed address when the user presses Search: a mutation, not a query, so it only
 * runs when asked (no lookup while typing, as Nominatim's usage policy requires).
 *
 * A mutation keeps what was typed (its variables) and the matches in TanStack Query's
 * mutation cache, by default for 5 minutes after it settles. `gcTime: 0` drops them as soon
 * as nothing is using them, and AddressSearch resets it once a match is picked.
 */
export function useFindPlaces() {
  return useMutation<{ places: Place[] }, ApiError, string>({ mutationFn: findPlaces, gcTime: 0 });
}
