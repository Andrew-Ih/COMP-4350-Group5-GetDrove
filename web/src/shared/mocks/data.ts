import type { components as Accounts } from "@/shared/api/generated/accounts";
import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";

// Sample data for the mock API, typed against the contracts: if a contract changes,
// these stop compiling, so the mocks can't silently drift from the real API.

export const maya = {
  id: "7a0c8d8e-3c38-4a5e-9a59-1d1f0b7f6b11",
  email: "maya@myumanitoba.ca",
  firstName: "Maya",
  lastName: "Singh",
  emailVerified: true,
  roles: ["user"],
} satisfies Accounts["schemas"]["User"];

const campus = { label: "University Centre", lat: 49.8075, lng: -97.1366 } satisfies Trips["schemas"]["Place"];

type Direction = Trips["schemas"]["Direction"];
type SearchResult = Trips["schemas"]["SearchResult"];
type RouteFeature = Routing["schemas"]["RouteFeature"];

const TRIP_SECONDS = 24 * 60;
const TRIP_METERS = 14_000;

function trip(id: string, departureAt: string, arrivalAt: string, seatsAvailable: number, direction: Direction = "to_campus") {
  return {
    id,
    driverId: `driver-${id}`,
    direction,
    // Riders only get the campus end; the driver's own end is private (null).
    origin: direction === "to_campus" ? null : campus,
    destination: direction === "to_campus" ? campus : null,
    departureAt,
    estimatedArrivalAt: arrivalAt,
    durationSeconds: TRIP_SECONDS,
    distanceMeters: TRIP_METERS,
    seatsTotal: 3,
    seatsAvailable,
    status: "scheduled",
  } satisfies Trips["schemas"]["Trip"];
}

/**
 * Four drivers passing near the rider, made up for the mock API. Each pickup is a short
 * walk from wherever the rider searched, in a different direction, and sits on that
 * trip's own route. Labels say where the pickup is relative to the rider, because the
 * mock doesn't know street names. Times fit the contract's search window: arriving in the
 * hour before an arrive-by time, or leaving in the hour after a leave-after time.
 */
const OFFERS = [
  // bearing: where the pickup is from the rider (degrees, 0 = north); start: where the
  // driver comes from, in metres east and north of the pickup.
  { id: "11111111-1111-4111-8111-111111111111", label: "Pickup north of you", bearing: 0, walkSeconds: 300, seats: 1, cents: 460, km: 10.2, minutes: 22, start: [-2600, 1800] },
  { id: "22222222-2222-4222-8222-222222222222", label: "Pickup west of you", bearing: 270, walkSeconds: 180, seats: 2, cents: 420, km: 9.3, minutes: 14, start: [-3200, -400] },
  { id: "33333333-3333-4333-8333-333333333333", label: "Pickup south of you", bearing: 180, walkSeconds: 420, seats: 3, cents: 380, km: 8.4, minutes: 8, start: [600, 2600] },
  { id: "44444444-4444-4444-8444-444444444444", label: "Pickup east of you", bearing: 90, walkSeconds: 240, seats: 2, cents: 440, km: 9.8, minutes: 30, start: [2800, 1200] },
] as const;

const WALK_METERS_PER_SECOND = 1.0; // a little under walking pace: streets aren't straight lines

/** The point `east` and `north` metres away from `from`. */
function offset([lng, lat]: [number, number], east: number, north: number): [number, number] {
  const metersPerDegree = 111_320;
  return [lng + east / (metersPerDegree * Math.cos((lat * Math.PI) / 180)), lat + north / metersPerDegree];
}

/** Search results for a search, plus each trip's route for GET /routing/trips/{id}/geometry. */
export function searchResultsFor(query: { lat: number; lng: number; direction: Direction; time: string }) {
  const time = Date.parse(query.time);
  const minutes = (n: number) => n * 60_000;
  const results: SearchResult[] = [];
  const routes = new Map<string, RouteFeature>();

  for (const offer of OFFERS) {
    const walk = offer.walkSeconds * WALK_METERS_PER_SECOND;
    const angle = (offer.bearing * Math.PI) / 180;
    const pickup = offset([query.lng, query.lat], walk * Math.sin(angle), walk * Math.cos(angle));
    const departure =
      query.direction === "to_campus" ? time - minutes(offer.minutes) - TRIP_SECONDS * 1000 : time + minutes(offer.minutes);
    results.push({
      trip: trip(offer.id, new Date(departure).toISOString(), new Date(departure + TRIP_SECONDS * 1000).toISOString(), offer.seats, query.direction),
      pickup: { label: offer.label, lat: pickup[1], lng: pickup[0], walkSeconds: offer.walkSeconds },
      cost: { amountCents: offer.cents, currency: "CAD", explanation: `${offer.km} km at $0.45/km` },
    });

    // The driver's end, through the pickup, then a bend towards campus. Straight lines:
    // the mock has no road network. Real routes come from OSRM and follow the roads.
    const driverEnd = offset(pickup, offer.start[0], offer.start[1]);
    const bend: [number, number] = [(pickup[0] + campus.lng) / 2 + 0.004, (pickup[1] + campus.lat) / 2];
    const toCampus: [number, number][] = [driverEnd, pickup, bend, [campus.lng, campus.lat]];
    routes.set(offer.id, {
      type: "Feature",
      geometry: { type: "LineString", coordinates: query.direction === "to_campus" ? toCampus : [...toCampus].reverse() },
      properties: { tripId: offer.id, distanceMeters: TRIP_METERS, durationSeconds: TRIP_SECONDS },
    });
  }

  results.sort((a, b) => Date.parse(a.trip.departureAt) - Date.parse(b.trip.departureAt)); // soonest first
  return { results, routes };
}

export const myTrips = [
  trip("55555555-5555-4555-8555-555555555555", "2026-10-20T12:35:00Z", "2026-10-20T12:57:00Z", 3),
] satisfies Trips["schemas"]["Trip"][];
