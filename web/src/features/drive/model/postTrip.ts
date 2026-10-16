import type { components } from "@/shared/api/generated/trips";
import type { LngLat } from "@/shared/map";

import { areaName, type Direction, isInServiceArea, toSearchTime } from "@/features/ride";

export type PostTripRequest = components["schemas"]["PostTripRequest"];
export type Trip = components["schemas"]["Trip"];

/** Seats a driver can offer, from the contract (1 to 6). */
export const SEAT_OPTIONS = [1, 2, 3, 4, 5, 6] as const;
export const DEFAULT_SEATS = 3;

/** What the driver's end of the trip is called, and the campus end, for each direction. */
export const ENDS: Record<Direction, { place: string; campus: string }> = {
  to_campus: { place: "Starting area", campus: "Destination" },
  from_campus: { place: "Destination area", campus: "Starting from" },
};

/** "2026-10-16", in the device's time zone. */
function toDateInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Tomorrow, leaving at 7:45 AM for campus or 4:45 PM from it. */
export function defaultDeparture(direction: Direction, now: Date = new Date()): { date: string; time: string } {
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  return { date: toDateInput(tomorrow), time: direction === "to_campus" ? "07:45" : "16:45" };
}

/**
 * The label saved with the driver's place: the neighbourhood ("Wolseley area"), never an
 * address. The contract keeps it private: only the driver ever sees it.
 */
export function placeLabel(point: LngLat): string {
  const area = areaName(point);
  return area ? `${area} area` : "Your chosen spot";
}

export type TripForm = {
  direction: Direction;
  point: LngLat | undefined;
  date: string;
  time: string;
  seats: number;
};

export type FormProblem = { field: "place" | "departure" | "seats"; message: string };

/**
 * The request for POST /api/trips/ from what the driver chose, or what to fix first.
 * The same rules the API checks, so most mistakes are caught before posting.
 */
export function buildPostTrip(form: TripForm, now: Date = new Date()): { body: PostTripRequest } | { problem: FormProblem } {
  if (!form.point) {
    return { problem: { field: "place", message: "Tap the map or use your location to choose where you start." } };
  }
  if (!isInServiceArea(form.point)) {
    return { problem: { field: "place", message: "GetDrove only covers Winnipeg for now. Choose a spot closer to campus." } };
  }
  const departureAt = toSearchTime(form.date, form.time);
  if (!departureAt) {
    return { problem: { field: "departure", message: "Choose a date and departure time." } };
  }
  if (Date.parse(departureAt) <= now.getTime()) {
    return { problem: { field: "departure", message: "Choose a departure time in the future." } };
  }
  if (!Number.isInteger(form.seats) || form.seats < 1 || form.seats > 6) {
    return { problem: { field: "seats", message: "Offer between 1 and 6 seats." } };
  }
  const [lng, lat] = form.point;
  return {
    body: {
      direction: form.direction,
      place: { label: placeLabel(form.point), lat, lng },
      departureAt,
      seatsTotal: form.seats,
    },
  };
}

/**
 * How close to another of the driver's trips a new departure may be. A new trip can't
 * leave less than this before another one departs, or before another one has arrived.
 */
export const OVERLAP_MARGIN_MINUTES = 30;

/**
 * The driver's trip that a new departure would clash with, if any: one still scheduled or
 * under way, whose time from (departure − margin) to arrival includes the new departure.
 * A warning only; the server should enforce the same rule (a contract change to come).
 */
export function findOverlap(trips: Trip[], departureAt: string): Trip | undefined {
  const departs = Date.parse(departureAt);
  const margin = OVERLAP_MARGIN_MINUTES * 60_000;
  return trips.find(
    (trip) =>
      (trip.status === "scheduled" || trip.status === "in_progress") &&
      departs > Date.parse(trip.departureAt) - margin &&
      departs < Date.parse(trip.estimatedArrivalAt),
  );
}

/** "You already have a trip at 7:45 AM on Fri, Oct 16. Choose a different time." */
export function overlapMessage(trip: Trip): string {
  return `You already have a trip at ${formatClock(trip.departureAt)} on ${formatDay(trip.departureAt)}. Choose a different time.`;
}

/** "7:35 AM", in the driver's time zone. */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours();
  return `${hours % 12 || 12}:${String(date.getMinutes()).padStart(2, "0")} ${hours < 12 ? "AM" : "PM"}`;
}

/** "Tue, Oct 20", in the driver's time zone. */
export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

/** 1320 → "22 min"; 3900 → "1 h 5 min". */
export function formatDuration(seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} min`;
  const rest = minutes % 60;
  return rest ? `${Math.floor(minutes / 60)} h ${rest} min` : `${minutes / 60} h`;
}

/** 14_200 → "14 km"; 9_340 → "9.3 km". */
export function formatDistance(meters: number): string {
  const km = meters / 1000;
  return km >= 10 ? `${Math.round(km)} km` : `${km.toFixed(1)} km`;
}
