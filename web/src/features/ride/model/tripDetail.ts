import type { components as Accounts } from "@/shared/api/generated/accounts";
import type { components as Trips } from "@/shared/api/generated/trips";

import { dayLabel, formatClock } from "./results";
import { type SearchQuery, toQueryString } from "./search";

export type TripDetail = Trips["schemas"]["TripDetail"];
export type PickupOption = Trips["schemas"]["PickupOption"];
export type DriverProfile = Accounts["schemas"]["PublicProfile"];
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
