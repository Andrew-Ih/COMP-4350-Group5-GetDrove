import { describe, expect, it } from "vitest";

import { boundsOf, CAMPUS, circlePolygon } from "./geo";

describe("circlePolygon", () => {
  it("returns a closed ring", () => {
    const ring = circlePolygon(CAMPUS, 500, 16);
    expect(ring).toHaveLength(17);
    expect(ring[0]).toEqual(ring[16]);
  });

  it("puts every point about the radius away from the centre", () => {
    const [lng, lat] = CAMPUS;
    for (const [x, y] of circlePolygon(CAMPUS, 500, 16)) {
      const dy = (y - lat) * 111_195;
      const dx = (x - lng) * 111_195 * Math.cos((lat * Math.PI) / 180);
      expect(Math.hypot(dx, dy)).toBeCloseTo(500, -1);
    }
  });
});

describe("boundsOf", () => {
  it("finds the south-west and north-east corners", () => {
    expect(
      boundsOf([
        [-97.1, 49.9],
        [-97.2, 49.8],
        [-97.15, 49.85],
      ]),
    ).toEqual([
      [-97.2, 49.8],
      [-97.1, 49.9],
    ]);
  });

  it("rejects an empty list", () => {
    expect(() => boundsOf([])).toThrow();
  });
});
