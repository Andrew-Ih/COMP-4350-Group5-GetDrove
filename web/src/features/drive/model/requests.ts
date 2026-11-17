import type { components } from "@/shared/api/generated/trips";

import { formatClock, formatDay, type Trip } from "./postTrip";

export type DriverRequest = components["schemas"]["DriverRequestView"];
export type TripDetail = components["schemas"]["TripDetail"];

/** The driver's page for one of their trips, with its requests. */
export function tripRequestsHref(tripId: string): string {
  return `/drive/trips/${tripId}`;
}

/**
 * The extra driving time a pickup adds: "+3 min", rounded up so a short detour isn't shown
 * as none. Undefined when it couldn't be worked out (the contract sends null): the screen
 * shows an error then, never a number.
 */
export function formatDetour(seconds: number | null): string | undefined {
  if (seconds === null) return undefined;
  if (seconds < 30) return "No detour";
  return `+${Math.ceil(seconds / 60)} min`;
}

/** "★ 4.9 · 0 no-shows", or "New rider · 1 no-show" without ratings. */
export function riderLine(rider: DriverRequest["rider"]): string {
  const rating = rider.rating === null ? "New rider" : `★ ${rider.rating.toFixed(1)}`;
  return `${rating} · ${rider.noShowCount} ${rider.noShowCount === 1 ? "no-show" : "no-shows"}`;
}

/** Pending requests (oldest first, as sent) and accepted riders (in pickup order). */
export function splitRequests(requests: DriverRequest[]) {
  const pending = requests.filter((r) => r.status === "pending");
  const accepted = requests
    .filter((r) => r.status === "accepted")
    .sort((a, b) => (a.pickupOrder ?? Number.MAX_SAFE_INTEGER) - (b.pickupOrder ?? Number.MAX_SAFE_INTEGER));
  return { pending, accepted };
}

/** "Tue, Oct 6 · Departs 7:35 AM". */
export function departureLine(trip: Trip): string {
  return `${formatDay(trip.departureAt)} · Departs ${formatClock(trip.departureAt)}`;
}

/** "Wolseley Ave & Arlington St → U of M Fort Garry", from the ends the driver gets back. */
export function routeLine(trip: Trip): string {
  const name = (place: Trip["origin"]) => place?.label ?? "U of M Fort Garry";
  return `${name(trip.origin)} → ${name(trip.destination)}`;
}

/** "2 of 3 seats filled". */
export function seatsFilled(trip: Trip): string {
  return `${trip.seatsTotal - trip.seatsAvailable} of ${trip.seatsTotal} seats filled`;
}

/** "1 seat left", "No seats left". */
export function seatsLeftLine(trip: Trip): string {
  if (trip.seatsAvailable === 0) return "No seats left";
  return `${trip.seatsAvailable} ${trip.seatsAvailable === 1 ? "seat" : "seats"} left`;
}

/** "1st pickup", "2nd pickup"… */
export function pickupOrderLabel(order: number | null): string | undefined {
  if (order === null) return undefined;
  const suffix = order % 100 >= 11 && order % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[order % 10] ?? "th");
  return `${order}${suffix} pickup`;
}

/**
 * Whether the driver can still decide on requests: the trip is scheduled and hasn't left.
 * Otherwise the list is shown without Accept and Decline.
 */
export function canDecide(trip: Trip, now: Date = new Date()): boolean {
  return trip.status === "scheduled" && Date.parse(trip.departureAt) > now.getTime();
}

/** The trip and its requests after a decision, so the screen updates before they're refetched. */
export function applyDecision(
  trip: Trip,
  requests: DriverRequest[],
  requestId: string,
  decision: "accepted" | "declined",
): { trip: Trip; requests: DriverRequest[] } {
  const request = requests.find((r) => r.id === requestId);
  if (!request) return { trip, requests };
  if (decision === "accepted") {
    if (request.status !== "pending") return { trip, requests };
    const order = requests.filter((r) => r.status === "accepted").length + 1;
    return {
      trip: { ...trip, seatsAvailable: Math.max(0, trip.seatsAvailable - 1) },
      requests: requests.map((r) => (r.id === requestId ? { ...r, status: "accepted", pickupOrder: order } : r)),
    };
  }
  // Declined requests leave the list; declining an accepted rider frees their seat.
  return {
    trip: request.status === "accepted" ? { ...trip, seatsAvailable: Math.min(trip.seatsTotal, trip.seatsAvailable + 1) } : trip,
    requests: requests.filter((r) => r.id !== requestId),
  };
}
