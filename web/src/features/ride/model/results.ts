import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";
import type { LngLat } from "@/shared/map";

import { areaName, type SearchQuery, WHEN_LABEL } from "./search";

export type SearchResult = Trips["schemas"]["SearchResult"];
export type RouteFeature = Routing["schemas"]["RouteFeature"];

export type SortBy = "departure" | "price" | "walk";

export const SORT_LABEL: Record<SortBy, string> = {
  departure: "Soonest",
  price: "Cheapest",
  walk: "Shortest walk",
};

/**
 * The results in the order the rider picked. The API already sends them soonest first;
 * "Cheapest" puts results without a price last, and ties keep the soonest first.
 */
export function sortResults(results: SearchResult[], by: SortBy): SearchResult[] {
  const departure = (r: SearchResult) => Date.parse(r.trip.departureAt);
  const key: Record<SortBy, (r: SearchResult) => number> = {
    departure,
    price: (r) => r.cost?.amountCents ?? Number.POSITIVE_INFINITY,
    walk: (r) => r.pickup.walkSeconds,
  };
  return [...results].sort((a, b) => key[by](a) - key[by](b) || departure(a) - departure(b));
}

/** 420 → "$4.20". The contract's only currency is CAD. */
export function formatMoney(amountCents: number): string {
  return `$${(amountCents / 100).toFixed(2)}`;
}

/** 240 → "4 min walk". Rounded up, so a 30-second walk is "1 min walk". */
export function formatWalk(walkSeconds: number): string {
  return `${Math.max(1, Math.ceil(walkSeconds / 60))} min walk`;
}

/** "7:48 AM", in the rider's time zone. */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours % 12 || 12}:${minutes} ${hours < 12 ? "AM" : "PM"}`;
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "today", "tomorrow" or "Tue, Oct 20", in the rider's time zone. */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const day = new Date(iso);
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  if (sameDay(day, now)) return "today";
  if (sameDay(day, tomorrow)) return "tomorrow";
  return day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

const CAMPUS_SHORT = "U of M Fort Garry";

/** The summary at the top: "Osborne Village → U of M Fort Garry" and "Tomorrow · arrive by 8:30 AM". */
export function searchSummary(query: SearchQuery, now: Date = new Date()): { route: string; when: string } {
  const area = areaName([query.lng, query.lat]) ?? "Your area";
  const route = query.direction === "to_campus" ? `${area} → ${CAMPUS_SHORT}` : `${CAMPUS_SHORT} → ${area}`;
  const day = dayLabel(query.time, now);
  const when = `${day.charAt(0).toUpperCase()}${day.slice(1)} · ${WHEN_LABEL[query.direction].toLowerCase()} ${formatClock(query.time)}`;
  return { route, when };
}

/** "4 trips tomorrow", "1 trip today", "No trips on Tue, Oct 20". */
export function resultsHeading(count: number, query: SearchQuery, now: Date = new Date()): string {
  const day = dayLabel(query.time, now);
  const when = day === "today" || day === "tomorrow" ? day : `on ${day}`;
  if (count === 0) return `No trips ${when}`;
  return `${count} ${count === 1 ? "trip" : "trips"} ${when}`;
}

/** "1 seat left", "3 seats left". */
export function seatsLeft(seats: number): string {
  return `${seats} ${seats === 1 ? "seat" : "seats"} left`;
}

/** A route's points from the Routing service, in the map's [lng, lat] order. */
export function routeCoordinates(route: RouteFeature): LngLat[] {
  return route.geometry.coordinates.map(([lng, lat]) => [lng, lat] as LngLat);
}
