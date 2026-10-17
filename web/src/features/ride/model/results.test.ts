import { describe, expect, it } from "vitest";

import {
  dayLabel,
  formatClock,
  formatMoney,
  formatWalk,
  resultsHeading,
  routeCoordinates,
  searchSummary,
  seatsLeft,
  type SearchResult,
  sortResults,
} from "./results";
import type { SearchQuery } from "./search";

// Local times, so the tests pass in any time zone.
const at = (date: string, time: string) => new Date(`${date}T${time}`).toISOString();
const NOW = new Date("2026-10-15T20:00:00");

function result(id: string, departs: string, cents: number | null, walkSeconds: number): SearchResult {
  return {
    trip: {
      id,
      driverId: `driver-${id}`,
      direction: "to_campus",
      origin: null,
      destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
      departureAt: at("2026-10-16", departs),
      estimatedArrivalAt: at("2026-10-16", "08:20"),
      durationSeconds: 1440,
      distanceMeters: 14_000,
      seatsTotal: 3,
      seatsAvailable: 2,
      status: "scheduled",
    },
    pickup: { label: "Osborne St & River Ave", lat: 49.8786, lng: -97.1445, walkSeconds },
    cost: cents === null ? null : { amountCents: cents, currency: "CAD", explanation: "9.3 km at $0.45/km" },
  };
}

const query: SearchQuery = { lat: 49.8768, lng: -97.1438, direction: "to_campus", time: at("2026-10-16", "08:30") };

describe("sortResults", () => {
  const early = result("early", "07:40", 460, 400);
  const cheap = result("cheap", "07:50", 380, 900);
  const noPrice = result("no-price", "07:45", null, 100);
  const all = [cheap, noPrice, early];

  it("sorts by departure, soonest first", () => {
    expect(sortResults(all, "departure").map((r) => r.trip.id)).toEqual(["early", "no-price", "cheap"]);
  });

  it("sorts by price, with trips that have no price last", () => {
    expect(sortResults(all, "price").map((r) => r.trip.id)).toEqual(["cheap", "early", "no-price"]);
  });

  it("sorts by walk, shortest first", () => {
    expect(sortResults(all, "walk").map((r) => r.trip.id)).toEqual(["no-price", "early", "cheap"]);
  });

  it("keeps ties in departure order and doesn't change the list it was given", () => {
    const sameWalk = [result("b", "07:50", 400, 300), result("a", "07:40", 400, 300)];
    expect(sortResults(sameWalk, "walk").map((r) => r.trip.id)).toEqual(["a", "b"]);
    expect(sameWalk.map((r) => r.trip.id)).toEqual(["b", "a"]);
  });
});

describe("formatting", () => {
  it("formats cents as dollars", () => {
    expect(formatMoney(420)).toBe("$4.20");
    expect(formatMoney(200)).toBe("$2.00");
    expect(formatMoney(1205)).toBe("$12.05");
  });

  it("rounds a walk up to whole minutes", () => {
    expect(formatWalk(240)).toBe("4 min walk");
    expect(formatWalk(241)).toBe("5 min walk");
    expect(formatWalk(20)).toBe("1 min walk");
    expect(formatWalk(0)).toBe("1 min walk");
  });

  it("shows clock times in the rider's time zone", () => {
    expect(formatClock(at("2026-10-16", "07:48"))).toBe("7:48 AM");
    expect(formatClock(at("2026-10-16", "12:05"))).toBe("12:05 PM");
    expect(formatClock(at("2026-10-16", "00:30"))).toBe("12:30 AM");
    expect(formatClock(at("2026-10-16", "16:30"))).toBe("4:30 PM");
  });

  it("names today and tomorrow, and dates further away", () => {
    expect(dayLabel(at("2026-10-15", "21:00"), NOW)).toBe("today");
    expect(dayLabel(at("2026-10-16", "08:30"), NOW)).toBe("tomorrow");
    expect(dayLabel(at("2026-10-20", "08:30"), NOW)).toBe("Tue, Oct 20");
  });

  it("counts seats", () => {
    expect(seatsLeft(1)).toBe("1 seat left");
    expect(seatsLeft(3)).toBe("3 seats left");
  });
});

describe("searchSummary", () => {
  it("goes from the rider's area to campus, arriving by their time", () => {
    expect(searchSummary(query, NOW)).toEqual({
      route: "Osborne Village → U of M Fort Garry",
      when: "Tomorrow · arrive by 8:30 AM",
    });
  });

  it("goes from campus to the rider's area, leaving after their time", () => {
    const fromCampus: SearchQuery = { ...query, direction: "from_campus", time: at("2026-10-20", "16:30") };
    expect(searchSummary(fromCampus, NOW)).toEqual({
      route: "U of M Fort Garry → Osborne Village",
      when: "Tue, Oct 20 · leave after 4:30 PM",
    });
  });

  it("calls an area without a nearby neighbourhood 'Your area'", () => {
    expect(searchSummary({ ...query, lat: 49.7, lng: -97.4 }, NOW).route).toBe("Your area → U of M Fort Garry");
  });
});

describe("resultsHeading", () => {
  it("counts trips on the search day", () => {
    expect(resultsHeading(4, query, NOW)).toBe("4 trips tomorrow");
    expect(resultsHeading(1, query, NOW)).toBe("1 trip tomorrow");
    expect(resultsHeading(0, query, NOW)).toBe("No trips tomorrow");
    expect(resultsHeading(2, { ...query, time: at("2026-10-20", "08:30") }, NOW)).toBe("2 trips on Tue, Oct 20");
  });
});

it("reads the route's points in the map's order", () => {
  expect(
    routeCoordinates({
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[-97.15, 49.88], [-97.1366, 49.8075]] },
      properties: { tripId: "t", distanceMeters: 1, durationSeconds: 1 },
    }),
  ).toEqual([[-97.15, 49.88], [-97.1366, 49.8075]]);
});
