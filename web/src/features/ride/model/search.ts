import type { components } from "@/shared/api/generated/trips";
import { CAMPUS, type LngLat } from "@/shared/map";

import { NEIGHBOURHOODS } from "./neighbourhoods";

/** to_campus or from_campus, from the Trips contract. */
export type Direction = components["schemas"]["Direction"];

/** How far from campus a rider can search from. Beyond this, GetDrove doesn't operate. */
export const SERVICE_RADIUS_METERS = 35_000;

/** How close a neighbourhood centre must be to name the area after it. */
const NAMING_RADIUS_METERS = 2_500;

/** The size of the "your area" circle on the map. Display only. */
export const AREA_RADIUS_METERS = 400;

/** Straight-line distance between two points, in metres (haversine). */
export function distanceMeters([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(a));
}

/** The name of the nearest neighbourhood, or undefined if none is close. */
export function areaName(point: LngLat): string | undefined {
  let best: { name: string; distance: number } | undefined;
  for (const { name, center } of NEIGHBOURHOODS) {
    const distance = distanceMeters(point, center);
    if (!best || distance < best.distance) best = { name, distance };
  }
  return best && best.distance <= NAMING_RADIUS_METERS ? best.name : undefined;
}

export function isInServiceArea(point: LngLat): boolean {
  return distanceMeters(point, CAMPUS) <= SERVICE_RADIUS_METERS;
}

/** What the "When" field means for each direction, matching `time` in the contract. */
export const WHEN_LABEL: Record<Direction, string> = {
  to_campus: "Arrive by",
  from_campus: "Leave after",
};

/** "2026-10-16", in the device's time zone. */
function toDateInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Tomorrow, arriving by 8:30 AM for campus or leaving after 4:30 PM from it. */
export function defaultWhen(direction: Direction, now: Date = new Date()): { date: string; time: string } {
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  return { date: toDateInput(tomorrow), time: direction === "to_campus" ? "08:30" : "16:30" };
}

/** Today's date for the date picker's minimum. */
export function today(now: Date = new Date()): string {
  return toDateInput(now);
}

/**
 * The date and time the rider picked (in their own time zone) as the contract wants it:
 * ISO 8601 in UTC, e.g. "2026-10-16T13:30:00.000Z". Undefined if the inputs are incomplete.
 */
export function toSearchTime(date: string, time: string): string | undefined {
  if (!date || !time) return undefined;
  const local = new Date(`${date}T${time}`);
  return Number.isNaN(local.getTime()) ? undefined : local.toISOString();
}

export type SearchQuery = { lat: number; lng: number; direction: Direction; time: string };

/** The query string for GET /api/trips/search and the results page. */
export function toQueryString({ lat, lng, direction, time }: SearchQuery): string {
  return new URLSearchParams({
    lat: lat.toFixed(5),
    lng: lng.toFixed(5),
    direction,
    time,
  }).toString();
}

/** Reads a search back from the results page's URL. Undefined if anything is missing or wrong. */
export function fromQueryString(params: URLSearchParams): SearchQuery | undefined {
  const lat = Number(params.get("lat"));
  const lng = Number(params.get("lng"));
  const direction = params.get("direction");
  const time = params.get("time");
  if (
    !params.get("lat") ||
    !params.get("lng") ||
    !Number.isFinite(lat) ||
    !Number.isFinite(lng) ||
    Math.abs(lat) > 90 ||
    Math.abs(lng) > 180 ||
    (direction !== "to_campus" && direction !== "from_campus") ||
    !time ||
    Number.isNaN(Date.parse(time))
  ) {
    return undefined;
  }
  return { lat, lng, direction, time };
}
