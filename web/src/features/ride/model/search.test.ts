import { describe, expect, it } from "vitest";

import { CAMPUS } from "@/shared/map";

import {
  areaName,
  defaultWhen,
  distanceMeters,
  fromQueryString,
  fromSearchTime,
  isInServiceArea,
  toQueryString,
  toSearchTime,
} from "./search";

describe("distanceMeters", () => {
  it("is zero for the same point and about 11 km for 0.1° of latitude", () => {
    expect(distanceMeters(CAMPUS, CAMPUS)).toBe(0);
    expect(distanceMeters([-97.1, 49.8], [-97.1, 49.9])).toBeCloseTo(11_120, -2);
  });
});

describe("areaName", () => {
  it("names a point near a neighbourhood centre", () => {
    expect(areaName([-97.1438, 49.8768])).toBe("Osborne Village");
  });

  it("gives no name far from every neighbourhood", () => {
    expect(areaName([-96.6, 50.3])).toBeUndefined();
  });
});

describe("isInServiceArea", () => {
  it("accepts Winnipeg and rejects places far away", () => {
    expect(isInServiceArea([-97.144, 49.877])).toBe(true);
    expect(isInServiceArea([-97.4, 49.2])).toBe(false);
  });
});

describe("defaultWhen", () => {
  const now = new Date(2026, 9, 15, 20, 0); // 15 Oct 2026, 8 PM local

  it("is tomorrow at 8:30 to campus and 4:30 PM from campus", () => {
    expect(defaultWhen("to_campus", now)).toEqual({ date: "2026-10-16", time: "08:30" });
    expect(defaultWhen("from_campus", now)).toEqual({ date: "2026-10-16", time: "16:30" });
  });

  it("rolls over the end of the month", () => {
    expect(defaultWhen("to_campus", new Date(2026, 9, 31, 9, 0)).date).toBe("2026-11-01");
  });
});

describe("toSearchTime", () => {
  it("turns the local date and time into UTC ISO 8601, as the contract wants", () => {
    expect(toSearchTime("2026-10-16", "08:30")).toBe(new Date(2026, 9, 16, 8, 30).toISOString());
  });

  it("is undefined while a field is empty", () => {
    expect(toSearchTime("", "08:30")).toBeUndefined();
    expect(toSearchTime("2026-10-16", "")).toBeUndefined();
  });
});

describe("fromSearchTime", () => {
  it("turns a search's time back into the date and time inputs", () => {
    const time = toSearchTime("2026-10-16", "08:30")!;
    expect(fromSearchTime(time)).toEqual({ date: "2026-10-16", time: "08:30" });
  });
});

describe("query string", () => {
  const search = { lat: 49.876812, lng: -97.143791, direction: "to_campus" as const, time: "2026-10-16T13:30:00.000Z" };

  it("round-trips, with the point rounded to about a metre", () => {
    const back = fromQueryString(new URLSearchParams(toQueryString(search)));
    expect(back).toEqual({ ...search, lat: 49.87681, lng: -97.14379 });
  });

  it.each([
    "lng=-97.1&direction=to_campus&time=2026-10-16T13:30:00Z",
    "lat=49.8&lng=-97.1&direction=sideways&time=2026-10-16T13:30:00Z",
    "lat=49.8&lng=-97.1&direction=to_campus&time=soon",
    "lat=north&lng=-97.1&direction=to_campus&time=2026-10-16T13:30:00Z",
  ])("rejects %j", (query) => {
    expect(fromQueryString(new URLSearchParams(query))).toBeUndefined();
  });
});
