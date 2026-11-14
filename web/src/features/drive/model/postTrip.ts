import type { components } from "@/shared/api/generated/trips";
import type { LngLat } from "@/shared/map";

import { areaName, type Direction, isInServiceArea, toSearchTime } from "@/features/ride";

export type PostTripRequest = components["schemas"]["PostTripRequest"];
export type PostTripSeriesRequest = components["schemas"]["PostTripSeriesRequest"];
export type TripSeriesResult = components["schemas"]["TripSeriesResult"];
export type Trip = components["schemas"]["Trip"];
export type Weekday = PostTripSeriesRequest["weekdays"][number];

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

export type FormProblem = { field: "place" | "departure" | "seats" | "repeat"; message: string };

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

// ---------------------------------------------------------------- repeating trips (#19)

/** The weekdays a trip can repeat on, Monday first, with how they're shown. */
export const WEEKDAYS: readonly { day: Weekday; short: string; long: string }[] = [
  { day: "mon", short: "Mon", long: "Monday" },
  { day: "tue", short: "Tue", long: "Tuesday" },
  { day: "wed", short: "Wed", long: "Wednesday" },
  { day: "thu", short: "Thu", long: "Thursday" },
  { day: "fri", short: "Fri", long: "Friday" },
];

/** How long a trip can repeat for, from its first departure (the contract's limit). */
export const MAX_REPEAT_WEEKS = 16;
/** The end date suggested when repeating is turned on: 4 weeks after the first trip. */
export const DEFAULT_REPEAT_WEEKS = 4;

const WINNIPEG = "America/Winnipeg";

/** "2026-11-16": the Winnipeg date of a moment, which the contract judges the days by. */
export function winnipegDate(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: WINNIPEG, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

/** The weekday of a "2026-11-16" date, or undefined for Saturday and Sunday. */
export function weekdayOf(date: string): Weekday | undefined {
  const day = new Date(`${date}T12:00:00Z`).getUTCDay(); // 0 = Sunday
  return day >= 1 && day <= 5 ? WEEKDAYS[day - 1]!.day : undefined;
}

/** "2026-11-16" plus `days` days. */
export function addDays(date: string, days: number): string {
  const moved = new Date(`${date}T12:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() + days);
  return moved.toISOString().slice(0, 10);
}

export type Repeat = { weekdays: Weekday[]; endDate: string };

/**
 * The request for POST /api/trips/series, or what to fix first. The same rules the API
 * checks: at least one weekday, the first trip on one of them (its Winnipeg day, #315), and
 * an end date after the first trip and at most 16 weeks after it.
 */
export function buildPostTripSeries(
  form: TripForm,
  repeat: Repeat,
  now: Date = new Date(),
): { body: PostTripSeriesRequest } | { problem: FormProblem } {
  const single = buildPostTrip(form, now);
  if ("problem" in single) return single;

  const firstDate = winnipegDate(single.body.departureAt);
  const firstDay = weekdayOf(firstDate);
  if (!firstDay) {
    return { problem: { field: "departure", message: "Repeating trips run Monday to Friday. Choose a weekday for your first trip." } };
  }
  if (repeat.weekdays.length === 0) {
    return { problem: { field: "repeat", message: "Pick at least one day to repeat on." } };
  }
  if (!repeat.weekdays.includes(firstDay)) {
    const name = WEEKDAYS.find((w) => w.day === firstDay)!.long;
    return { problem: { field: "repeat", message: `Your first trip is on a ${name}. Pick ${name} too, or change the date.` } };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(repeat.endDate)) {
    return { problem: { field: "repeat", message: "Choose the last day it repeats." } };
  }
  if (repeat.endDate <= firstDate) {
    return { problem: { field: "repeat", message: "The last day must be after your first trip." } };
  }
  if (repeat.endDate > addDays(firstDate, MAX_REPEAT_WEEKS * 7)) {
    return { problem: { field: "repeat", message: `A trip can repeat for up to ${MAX_REPEAT_WEEKS} weeks. Choose an earlier last day.` } };
  }

  const weekdays = WEEKDAYS.map((w) => w.day).filter((day) => repeat.weekdays.includes(day)); // Monday first
  return { body: { ...single.body, weekdays, endDate: repeat.endDate } };
}

/** "Mon, Wed and Fri". */
export function weekdayList(weekdays: readonly Weekday[]): string {
  const names = WEEKDAYS.filter((w) => weekdays.includes(w.day)).map((w) => w.short);
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : (names[0] ?? "");
}

/** "Wed, Nov 18", for a "2026-11-18" date. */
export function formatDate(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", { timeZone: "UTC", weekday: "short", month: "short", day: "numeric" });
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
