import type { components as Accounts } from "@/shared/api/generated/accounts";
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

function trip(id: string, departureAt: string, arrivalAt: string, seatsAvailable: number) {
  return {
    id,
    driverId: `driver-${id}`,
    direction: "to_campus",
    origin: null, // the driver's start is never shown to riders
    destination: campus,
    departureAt,
    estimatedArrivalAt: arrivalAt,
    durationSeconds: 1440,
    distanceMeters: 14_000,
    seatsTotal: 3,
    seatsAvailable,
    status: "scheduled",
  } satisfies Trips["schemas"]["Trip"];
}

export const searchResults = [
  {
    trip: trip("11111111-1111-4111-8111-111111111111", "2026-10-20T12:44:00Z", "2026-10-20T13:08:00Z", 1),
    pickup: { label: "Corydon Ave & Osborne St", lat: 49.8705, lng: -97.1443, walkSeconds: 300 },
    cost: { amountCents: 460, currency: "CAD", explanation: "10.2 km at $0.45/km" },
  },
  {
    trip: trip("22222222-2222-4222-8222-222222222222", "2026-10-20T12:48:00Z", "2026-10-20T13:12:00Z", 2),
    pickup: { label: "Osborne St & River Ave", lat: 49.8786, lng: -97.1445, walkSeconds: 240 },
    cost: { amountCents: 420, currency: "CAD", explanation: "9.2 km at $0.45/km" },
  },
] satisfies Trips["schemas"]["SearchResult"][];

export const myTrips = [
  trip("33333333-3333-4333-8333-333333333333", "2026-10-20T12:35:00Z", "2026-10-20T12:57:00Z", 3),
] satisfies Trips["schemas"]["Trip"][];
