import { type ApiError, NETWORK_ERROR } from "@/shared/api";
import type { components } from "@/shared/api/generated/routing";
import type { LngLat } from "@/shared/map";

/** A match for a typed address, from the Routing contract (#257). */
export type Place = components["schemas"]["Place"];

/** Shorter than this can't be an address; the contract refuses it too. */
export const MIN_QUERY_LENGTH = 3;

/** Where a match is, in the map's [longitude, latitude] order. */
export function placePoint(place: Place): LngLat {
  return [place.lng, place.lat];
}

export const NOT_FOUND_MESSAGE =
  "We couldn't find that in Winnipeg. Check the address, add the street type (St, Ave), or tap the map instead.";
export const TOO_SHORT_MESSAGE = "Type a street address or a place, like 750 Osborne St.";

/** What to tell the user when the lookup fails. Tapping the map always still works. */
export function placeErrorMessage(error: ApiError): string {
  if (error.code === NETWORK_ERROR) return "Check your connection and try again.";
  if (error.code === "invalid_input") return TOO_SHORT_MESSAGE;
  return "We can't look up addresses right now. Try again in a moment, or tap the map instead.";
}
