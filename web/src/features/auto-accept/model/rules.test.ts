import { describe, expect, it } from "vitest";

import { buildRules, ratingLabel, ratingOptions, rulesSummary } from "./rules";

describe("buildRules", () => {
  it("builds the rules to save", () => {
    expect(buildRules({ enabled: true, maxDetourMinutes: " 8 ", minRating: 4 })).toEqual({
      rules: { enabled: true, maxDetourMinutes: 8, minRating: 4 },
    });
  });

  it("keeps the values when turned off", () => {
    expect(buildRules({ enabled: false, maxDetourMinutes: "5", minRating: null })).toEqual({
      rules: { enabled: false, maxDetourMinutes: 5, minRating: null },
    });
  });

  it.each(["", "-1", "31", "2.5", "five"])("refuses a detour of %j", (maxDetourMinutes) => {
    expect(buildRules({ enabled: true, maxDetourMinutes, minRating: null })).toEqual({
      problem: { field: "maxDetourMinutes", message: "Enter a whole number of minutes from 0 to 30." },
    });
  });

  it("allows 0 and 30 minutes", () => {
    expect(buildRules({ enabled: true, maxDetourMinutes: "0", minRating: null })).toHaveProperty("rules");
    expect(buildRules({ enabled: true, maxDetourMinutes: "30", minRating: null })).toHaveProperty("rules");
  });

  it("refuses a rating outside 1 to 5", () => {
    expect(buildRules({ enabled: true, maxDetourMinutes: "5", minRating: 0.5 })).toMatchObject({ problem: { field: "minRating" } });
  });
});

describe("ratings", () => {
  it("offers the usual ratings, plus a saved one that isn't among them", () => {
    expect(ratingOptions(null)).toEqual([null, 3, 3.5, 4, 4.5]);
    expect(ratingOptions(4.2)).toEqual([null, 3, 3.5, 4, 4.2, 4.5]);
  });

  it("labels them", () => {
    expect(ratingLabel(null)).toBe("Any rating");
    expect(ratingLabel(4)).toBe("4.0 or higher");
  });
});

describe("rulesSummary", () => {
  it("says what the rules do", () => {
    expect(rulesSummary({ enabled: false, maxDetourMinutes: 5, minRating: null })).toBe(
      "Every request waits for you to accept or decline it.",
    );
    expect(rulesSummary({ enabled: true, maxDetourMinutes: 5, minRating: 4 })).toBe(
      "Requests that add at most 5 min, from riders rated 4.0 or higher (or new riders), are accepted for you while you have seats free.",
    );
    expect(rulesSummary({ enabled: true, maxDetourMinutes: 0, minRating: null })).toBe(
      "Requests that add no detour, from any rider, are accepted for you while you have seats free.",
    );
  });
});
