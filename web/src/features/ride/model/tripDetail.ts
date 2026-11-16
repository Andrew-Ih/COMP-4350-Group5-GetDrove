import type { components as Accounts } from "@/shared/api/generated/accounts";
import type { components as Trips } from "@/shared/api/generated/trips";

import { dayLabel, formatClock } from "./results";
import { type SearchQuery, toQueryString } from "./search";

export type TripDetail = Trips["schemas"]["TripDetail"];
export type PickupOption = Trips["schemas"]["PickupOption"];
export type DriverProfile = Accounts["schemas"]["PublicProfile"];
export type SeatRequest = Trips["schemas"]["SeatRequest"];
type Trip = Trips["schemas"]["Trip"];

/** The trip detail page for a trip from the results, keeping the search so "All trips" goes back to it. */
export function tripDetailHref(tripId: string, query: SearchQuery): string {
  return `/ride/trip/${tripId}?${toQueryString(query)}`;
}

/**
 * Whether a rider can still ask for a seat on this trip:
 * - open: scheduled, not left yet, with a seat free
 * - full: scheduled but no seats left
 * - cancelled: the driver cancelled it
 * - departed: under way, finished, or past its departure time
 */
export type Availability = "open" | "full" | "cancelled" | "departed";

export function availability(trip: Trip, now: Date = new Date()): Availability {
  if (trip.status === "cancelled") return "cancelled";
  if (trip.status !== "scheduled" || Date.parse(trip.departureAt) <= now.getTime()) return "departed";
  return trip.seatsAvailable === 0 ? "full" : "open";
}

/** "2 of 3 seats left · departs 7:48 AM tomorrow". */
export function seatsAndDeparture(trip: Trip, now: Date = new Date()): string {
  const day = dayLabel(trip.departureAt, now);
  const when = day === "today" || day === "tomorrow" ? day : `on ${day}`;
  return `${trip.seatsAvailable} of ${trip.seatsTotal} seats left · departs ${formatClock(trip.departureAt)} ${when}`;
}

type Vehicle = { make: string; model: string; colour: string; plate?: string };

/**
 * "★ 4.9 · Grey Honda Civic". The plate is added once the rider is accepted (the trip
 * detail only sends the vehicle with its plate then). Unknown parts are left out.
 */
export function driverLine(profile: DriverProfile | undefined, vehicle: Vehicle | null | undefined): string {
  const parts: string[] = [];
  if (profile) parts.push(profile.rating === null ? "New driver" : `★ ${profile.rating.toFixed(1)}`);
  const car = vehicle ?? profile?.vehicle;
  if (car) parts.push(`${car.colour} ${car.make} ${car.model}`);
  if (vehicle?.plate) parts.push(vehicle.plate);
  return parts.join(" · ");
}

/** How often a pending request is checked for the driver's decision. */
export const REQUEST_POLL_MS = 10_000;

/**
 * How many rejected pickup points the trip detail can be asked to leave out (#136): the
 * contract's limit for `exclude`, on the trip detail and on a seat request.
 */
export const MAX_EXCLUDED_PICKUPS = 20;

/**
 * The points to leave out after the rider says none of `pickups` work: the ones already
 * left out plus these. Undefined when that would go over the contract's limit, so there's
 * no "None of these work" to offer.
 */
export function afterRejecting(excluded: readonly string[], pickups: readonly PickupOption[]): string[] | undefined {
  const next = [...new Set([...excluded, ...pickups.map((p) => p.id)])];
  return next.length <= MAX_EXCLUDED_PICKUPS ? next : undefined;
}

/** Where a rider adds a payment card (#152). */
export const ADD_CARD_HREF = "/account/card";

/** A request that still holds (or is waiting for) a seat. */
export function isActive(request: SeatRequest | null | undefined): request is SeatRequest {
  return request?.status === "pending" || request?.status === "accepted";
}

type Message = { title: string; text: string; link?: { href: string; label: string } };

/**
 * What the rider is told when a request is over without a ride: the driver declined, it
 * expired, the payment hold failed, or they cancelled it. Undefined while it's still active.
 */
export function requestOutcome(request: SeatRequest, driver: string | undefined): Message | undefined {
  switch (request.status) {
    case "declined":
      return { title: `${driver ?? "The driver"} declined your request`, text: "You weren't charged. You can ask for a seat on another trip." };
    case "expired":
      return { title: "Your request expired", text: "The driver didn't answer before the trip. You weren't charged." };
    case "payment_failed":
      return {
        title: "Your payment didn't go through",
        text: "We couldn't hold the fare on your card, so the request was cancelled.",
        link: { href: ADD_CARD_HREF, label: "Update your card" },
      };
    case "cancelled":
      return { title: "Request cancelled", text: "You weren't charged." };
    default:
      return undefined;
  }
}

/**
 * What the rider is told when asking for a seat fails, by the API's error code. `here` is
 * this page's address, so adding a card comes back to it.
 */
export function requestSeatError(code: string | undefined, here: string): Message {
  switch (code) {
    case "trip_full":
      return { title: "Sorry, that seat was just taken", text: "Someone else got the last seat. Go back to see other trips." };
    case "overlapping_request":
      return {
        title: "You already have a ride around this time",
        text: "Cancel that request in My trips before asking for this one.",
        link: { href: "/trips", label: "Go to My trips" },
      };
    case "already_requested":
      return { title: "You've already asked for a seat on this trip", text: "Your request is shown below." };
    case "card_required":
      return {
        title: "Add a card first",
        text: "Your card is only charged if the driver accepts.",
        link: { href: `${ADD_CARD_HREF}?next=${encodeURIComponent(here)}`, label: "Add a card" },
      };
    case "trip_not_open":
      return { title: "This trip isn't taking requests anymore", text: "Go back to see other trips." };
    case "own_trip":
      return { title: "This is your own trip", text: "You can't ask for a seat on a trip you're driving." };
    case "pickup_not_available":
      return { title: "That pickup point isn't available anymore", text: "Choose another one and try again." };
    case "routing_unavailable":
    case "service_unavailable":
      return { title: "We couldn't confirm your pickup", text: "Matching is unavailable right now. Try again in a minute." };
    case "payments_unavailable":
      return { title: "We couldn't check your card or price", text: "Payments are unavailable right now. Try again in a minute." };
    case "trip_not_found":
      return { title: "This trip is no longer available", text: "Go back to see other trips." };
    default:
      return { title: "We couldn't send your request", text: "Something went wrong. Try again." };
  }
}

/** What the rider is told when cancelling fails. */
export function cancelRequestError(code: string | undefined): string {
  return code === "request_not_cancellable"
    ? "This request can't be cancelled anymore: the trip may have started."
    : "We couldn't cancel your request. Try again.";
}
