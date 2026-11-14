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
    driverId: driverIdOf(id),
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

type Offer = (typeof OFFERS)[number];

/** The drivers of the trips above, for GET /accounts/users/{id}/profile. One has no ratings yet. */
const DRIVERS: Record<string, Omit<Accounts["schemas"]["PublicProfile"], "id">> = {
  [OFFERS[0].id]: { firstName: "Amira", rating: 4.8, ratingCount: 31, tripCount: 40, isDriver: true, vehicle: { make: "Toyota", model: "Corolla", colour: "White" } },
  [OFFERS[1].id]: { firstName: "Priya", rating: 4.9, ratingCount: 52, tripCount: 61, isDriver: true, vehicle: { make: "Honda", model: "Civic", colour: "Grey" } },
  [OFFERS[2].id]: { firstName: "Daniel", rating: 5.0, ratingCount: 12, tripCount: 15, isDriver: true, vehicle: { make: "Mazda", model: "3", colour: "Red" } },
  [OFFERS[3].id]: { firstName: "Jordan", rating: null, ratingCount: 0, tripCount: 0, isDriver: true, vehicle: { make: "Kia", model: "Soul", colour: "Blue" } },
};

/** A trip's driver ID in the mocks. */
const driverIdOf = (tripId: string) => `driver-${tripId}`;

/** The public profile of a mock driver, or undefined for anyone else. */
export function driverProfile(userId: string): Accounts["schemas"]["PublicProfile"] | undefined {
  const tripId = userId.replace(/^driver-/, "");
  const driver = DRIVERS[tripId];
  return driver && { id: userId, ...driver };
}

const WALK_METERS_PER_SECOND = 1.0; // a little under walking pace: streets aren't straight lines

/** The point `east` and `north` metres away from `from`. */
function offset([lng, lat]: [number, number], east: number, north: number): [number, number] {
  const metersPerDegree = 111_320;
  return [lng + east / (metersPerDegree * Math.cos((lat * Math.PI) / 180)), lat + north / metersPerDegree];
}

type Search = { lat: number; lng: number; direction: Direction; time: string };

/**
 * Where an offer's trip goes for a rider searching from `query`: the trip, its pickup a
 * short walk from the rider, and its route. The route runs from the driver's end through
 * the pickup, then bends towards campus. Straight lines: the mock has no road network.
 * Real routes come from OSRM and follow the roads.
 */
function place(offer: Offer, query: Search) {
  const time = Date.parse(query.time);
  const minutes = (n: number) => n * 60_000;
  const walk = offer.walkSeconds * WALK_METERS_PER_SECOND;
  const angle = (offer.bearing * Math.PI) / 180;
  const pickup = offset([query.lng, query.lat], walk * Math.sin(angle), walk * Math.cos(angle));
  const departure =
    query.direction === "to_campus" ? time - minutes(offer.minutes) - TRIP_SECONDS * 1000 : time + minutes(offer.minutes);
  const driverEnd = offset(pickup, offer.start[0], offer.start[1]);
  const bend: [number, number] = [(pickup[0] + campus.lng) / 2 + 0.004, (pickup[1] + campus.lat) / 2];
  const toCampus: [number, number][] = [driverEnd, pickup, bend, [campus.lng, campus.lat]];
  const route: RouteFeature = {
    type: "Feature",
    geometry: { type: "LineString", coordinates: query.direction === "to_campus" ? toCampus : [...toCampus].reverse() },
    properties: { tripId: offer.id, distanceMeters: TRIP_METERS, durationSeconds: TRIP_SECONDS },
  };
  return {
    trip: trip(offer.id, new Date(departure).toISOString(), new Date(departure + TRIP_SECONDS * 1000).toISOString(), offer.seats, query.direction),
    pickup,
    driverEnd,
    bend,
    route,
  };
}

const cost = (cents: number, km: number): Trips["schemas"]["Cost"] => ({
  amountCents: cents,
  currency: "CAD",
  explanation: `${km.toFixed(1)} km at $0.45/km`,
});

/** Search results for a search, plus each trip's route for GET /routing/trips/{id}/geometry. */
export function searchResultsFor(query: Search) {
  const results: SearchResult[] = [];
  const routes = new Map<string, RouteFeature>();

  for (const offer of OFFERS) {
    const placed = place(offer, query);
    results.push({
      trip: placed.trip,
      pickup: { label: offer.label, lat: placed.pickup[1], lng: placed.pickup[0], walkSeconds: offer.walkSeconds },
      cost: cost(offer.cents, offer.km),
    });
    routes.set(offer.id, placed.route);
  }

  results.sort((a, b) => Date.parse(a.trip.departureAt) - Date.parse(b.trip.departureAt)); // soonest first
  return { results, routes };
}

/** The point a fraction `t` of the way from `a` to `b`. */
function between(a: [number, number], b: [number, number], t: number): [number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/** Straight-line metres between two [lng, lat] points (close enough at city scale). */
function metersBetween(a: [number, number], b: [number, number]): number {
  const metersPerDegree = 111_320;
  const east = (b[0] - a[0]) * metersPerDegree * Math.cos((a[1] * Math.PI) / 180);
  const north = (b[1] - a[1]) * metersPerDegree;
  return Math.hypot(east, north);
}

/**
 * GET /trips/{id}: the trip with up to 3 pickup points on its route, best first, leaving
 * out the ones in `exclude` (#136). Each trip has 6 points: the one from the search, then
 * others further back towards the driver's end or further on, so "None of these work" gives
 * 3 new ones once and then none. Picked up further back, the rider rides (and pays) a
 * little more. Without `rider`, no pickups. Undefined if the trip isn't one of the mock trips.
 */
export function tripDetailFor(
  tripId: string,
  rider: { lat: number; lng: number } | undefined,
  search: Omit<Search, "lat" | "lng">,
  exclude: readonly string[] = [],
) {
  const offer = OFFERS.find((o) => o.id === tripId);
  if (!offer) return undefined;
  const placed = place(offer, { lat: rider?.lat ?? campus.lat, lng: rider?.lng ?? campus.lng, ...search });
  const you: [number, number] = rider ? [rider.lng, rider.lat] : [campus.lng, campus.lat];

  const options: { label: string; point: [number, number]; extraKm: number }[] = [
    { label: offer.label, point: placed.pickup, extraKm: 0 },
    { label: `${offer.label}, further back`, point: between(placed.pickup, placed.driverEnd, 0.15), extraKm: 0.5 },
    { label: `${offer.label}, further on`, point: between(placed.pickup, placed.bend, 0.12), extraKm: -0.4 },
    { label: `${offer.label}, a little back`, point: between(placed.pickup, placed.driverEnd, 0.06), extraKm: 0.2 },
    { label: `${offer.label}, a little on`, point: between(placed.pickup, placed.bend, 0.05), extraKm: -0.2 },
    { label: `${offer.label}, near the corner`, point: between(placed.pickup, placed.bend, 0.09), extraKm: -0.3 },
  ];
  const pickups: Trips["schemas"]["PickupOption"][] = rider
    ? options
        .map((option, i) => {
          const km = offer.km + option.extraKm;
          return {
            id: `${offer.id.slice(0, 4)}-${i + 1}`,
            label: option.label,
            lat: option.point[1],
            lng: option.point[0],
            walkSeconds: i === 0 ? offer.walkSeconds : Math.round(metersBetween(you, option.point) / WALK_METERS_PER_SECOND),
            cost: cost(offer.cents + Math.round(option.extraKm * 45), km),
          };
        })
        .filter((option) => !exclude.includes(option.id))
        .slice(0, 3)
    : [];

  const detail: Trips["schemas"]["TripDetail"] = { trip: placed.trip, vehicle: null, pickups, myRequest: null };
  return { detail, route: placed.route };
}

export const myTrips = [
  trip("55555555-5555-4555-8555-555555555555", "2026-10-20T12:35:00Z", "2026-10-20T12:57:00Z", 3),
] satisfies Trips["schemas"]["Trip"][];

/** Whether a trip is one of the other drivers' trips that searches return. */
export function isSearchTrip(tripId: string): boolean {
  return OFFERS.some((o) => o.id === tripId);
}
