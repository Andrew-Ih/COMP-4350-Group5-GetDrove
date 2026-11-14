import { delay, http, HttpResponse } from "msw";

import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";

/**
 * Mock API for posting a trip (#96) and a repeating trip (#19), matching POST /api/trips/,
 * POST /api/trips/series and the route of a posted trip. Special inputs to try the error states:
 *   - a departure in the past              → 422 departure_in_past
 *   - a departure time ending in :55       → 503 routing_unavailable (nothing saved)
 * Posted trips are listed by GET /api/trips/mine?role=driver, so the "you already have a
 * trip then" warning can be tried too. A repeating trip skips the days that clash with
 * trips already posted (post a one-off trip first, then repeat over the same day).
 */

const CAMPUS = { label: "University Centre", lat: 49.8075, lng: -97.1366 };
const ROAD_FACTOR = 1.35; // roads are longer than a straight line
const METERS_PER_SECOND = 10; // about 36 km/h, city driving

// Trips posted in this session, and their routes for GET /routing/trips/{id}/geometry.
const postedTrips: Trips["schemas"]["Trip"][] = [];
const posted = new Map<string, Routing["schemas"]["RouteFeature"]>();

/** Forgets the trips posted so far (for tests). */
export function resetPostedTrips() {
  postedTrips.length = 0;
  posted.clear();
}

function straightLineMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

function problem(status: number, code: string, detail: string, extra: object = {}) {
  return HttpResponse.json(
    { type: "about:blank", title: detail, status, detail, instance: "/api/trips/", code, requestId: "mock", ...extra },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

type Trip = Trips["schemas"]["Trip"];

/** A trip for `body` leaving at `departure`, saved with its route. */
function createTrip(body: Trips["schemas"]["PostTripRequest"], departure: Date, seriesId?: string): Trip {
  const meters = Math.round(straightLineMeters(body.place, CAMPUS) * ROAD_FACTOR);
  const seconds = Math.round(meters / METERS_PER_SECOND);
  const trip: Trip = {
    id: crypto.randomUUID(),
    driverId: "7a0c8d8e-3c38-4a5e-9a59-1d1f0b7f6b11",
    direction: body.direction,
    // The driver gets their own end back; riders would get null.
    origin: body.direction === "to_campus" ? body.place : CAMPUS,
    destination: body.direction === "to_campus" ? CAMPUS : body.place,
    departureAt: departure.toISOString(),
    estimatedArrivalAt: new Date(departure.getTime() + seconds * 1000).toISOString(),
    durationSeconds: seconds,
    distanceMeters: meters,
    seatsTotal: body.seatsTotal,
    seatsAvailable: body.seatsTotal,
    status: "scheduled",
    seriesId: seriesId ?? null,
  };

  // A rough road-like line: east or west first, then south to campus. Real routes come
  // from OSRM and follow the roads.
  const corner: [number, number] = [CAMPUS.lng + 0.004, body.place.lat];
  const toCampus: [number, number][] = [[body.place.lng, body.place.lat], corner, [CAMPUS.lng, CAMPUS.lat]];
  posted.set(trip.id, {
    type: "Feature",
    geometry: { type: "LineString", coordinates: body.direction === "to_campus" ? toCampus : [...toCampus].reverse() },
    properties: { tripId: trip.id, distanceMeters: meters, durationSeconds: seconds },
  });
  postedTrips.push(trip);
  return trip;
}

/** The 422 or 503 for a departure the mock won't take, if any. */
function departureProblem(departure: Date) {
  if (departure.getTime() <= Date.now()) {
    return problem(422, "departure_in_past", "The departure must be in the future", {
      errors: [{ field: "departureAt", message: "Must be in the future" }],
    });
  }
  if (departure.getUTCMinutes() === 55) {
    return problem(503, "routing_unavailable", "The route couldn't be computed right now");
  }
  return undefined;
}

// ---------------------------------------------------------------- repeating trips (#19)

const WINNIPEG = "America/Winnipeg";
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"] as const;
const OVERLAP_MARGIN_MS = 30 * 60_000;

/** A moment's date and time on a Winnipeg clock. */
function winnipegClock(time: number) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: WINNIPEG,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
      .formatToParts(new Date(time))
      .map((p) => [p.type, p.value]),
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour), minute: Number(parts.minute) };
}

/** The moment it's `hour:minute` on `date` in Winnipeg, whether or not daylight time is on. */
function winnipegMoment(date: string, hour: number, minute: number): Date {
  const wanted = Date.parse(`${date}T00:00:00Z`) + (hour * 60 + minute) * 60_000;
  let guess = wanted + 6 * 3_600_000; // Winnipeg is 5 or 6 hours behind UTC
  for (let i = 0; i < 2; i++) {
    const clock = winnipegClock(guess);
    guess -= Date.parse(`${clock.date}T00:00:00Z`) + (clock.hour * 60 + clock.minute) * 60_000 - wanted;
  }
  return new Date(guess);
}

const weekdayOf = (date: string) => WEEKDAYS[new Date(`${date}T12:00:00Z`).getUTCDay() - 1];
const addDays = (date: string, days: number) => new Date(Date.parse(`${date}T12:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);

/** Whether the driver already has a trip around `departure` (the 30-minute rule of #96). */
function clashes(departure: Date): boolean {
  const departs = departure.getTime();
  return postedTrips.some(
    (trip) =>
      trip.status === "scheduled" &&
      departs > Date.parse(trip.departureAt) - OVERLAP_MARGIN_MS &&
      departs < Date.parse(trip.estimatedArrivalAt),
  );
}

const invalid = (field: string, message: string) =>
  problem(422, "invalid_input", "Invalid input", { errors: [{ field, message }] });

export const driveHandlers = [
  http.post("*/api/trips/", async ({ request }) => {
    const body = (await request.json()) as Trips["schemas"]["PostTripRequest"];
    await delay(); // realistic in the browser, none in tests
    const departure = new Date(body.departureAt);
    const refused = departureProblem(departure);
    if (refused) return refused;
    return HttpResponse.json(createTrip(body, departure), { status: 201 });
  }),

  // One trip per chosen weekday from the first departure to endDate, all at the same
  // Winnipeg time, skipping the days that clash with trips already posted.
  http.post("*/api/trips/series", async ({ request }) => {
    const body = (await request.json()) as Trips["schemas"]["PostTripSeriesRequest"];
    await delay();
    const first = new Date(body.departureAt);
    const refused = departureProblem(first);
    if (refused) return refused;

    const { weekdays, endDate } = body;
    const start = winnipegClock(first.getTime());
    if (weekdays.length === 0 || new Set(weekdays).size !== weekdays.length) {
      return invalid("weekdays", "Each weekday can only be listed once");
    }
    if (!weekdays.includes(weekdayOf(start.date)!)) {
      return invalid("weekdays", "The first departure must be on one of the chosen weekdays");
    }
    if (endDate <= start.date || endDate > addDays(start.date, 16 * 7)) {
      return invalid("endDate", "After the first departure and at most 16 weeks after it");
    }

    const seriesId = crypto.randomUUID();
    const trips: Trip[] = [];
    const skippedDates: string[] = [];
    for (let date = start.date; date <= endDate; date = addDays(date, 1)) {
      const day = weekdayOf(date);
      if (!day || !weekdays.includes(day)) continue;
      const departure = winnipegMoment(date, start.hour, start.minute);
      if (clashes(departure)) skippedDates.push(date);
      else trips.push(createTrip(body, departure, seriesId));
    }
    return HttpResponse.json({ seriesId, trips, skippedDates }, { status: 201 });
  }),

  // The driver's upcoming trips: the ones posted here, soonest first. role=rider falls
  // through to the next handler.
  http.get("*/api/trips/mine", ({ request }) => {
    const role = new URL(request.url).searchParams.get("role") ?? "driver";
    if (role !== "driver") return undefined;
    const upcoming = postedTrips
      .filter((trip) => Date.parse(trip.estimatedArrivalAt) > Date.now())
      .sort((a, b) => Date.parse(a.departureAt) - Date.parse(b.departureAt));
    return HttpResponse.json(upcoming);
  }),

  // Routes of trips posted here. Any other trip falls through to the next handler.
  http.get("*/api/routing/trips/:tripId/geometry", ({ params }) => {
    const route = posted.get(String(params.tripId));
    return route ? HttpResponse.json(route) : undefined;
  }),
];
