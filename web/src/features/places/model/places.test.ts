import { describe, expect, it } from "vitest";

import { ApiError, networkProblem } from "@/shared/api";
import { problem } from "@/shared/testing/render";

import { NOT_FOUND_MESSAGE, placeErrorMessage, placePoint, TOO_SHORT_MESSAGE } from "./places";

describe("places", () => {
  it("gives a match's point in the map's [lng, lat] order", () => {
    expect(placePoint({ label: "Polo Park", lat: 49.881, lng: -97.2005 })).toEqual([-97.2005, 49.881]);
  });

  it("explains each failure, always offering the map", () => {
    expect(placeErrorMessage(new ApiError(networkProblem()))).toBe("Check your connection and try again.");
    expect(placeErrorMessage(new ApiError(problem(422, "invalid_input", "Invalid")))).toBe(TOO_SHORT_MESSAGE);
    expect(placeErrorMessage(new ApiError(problem(503, "geocoding_unavailable", "Down")))).toMatch(/tap the map/);
    expect(placeErrorMessage(new ApiError(problem(502, "service_unavailable", "Down")))).toMatch(/tap the map/);
    expect(NOT_FOUND_MESSAGE).toMatch(/tap the map/);
  });
});
