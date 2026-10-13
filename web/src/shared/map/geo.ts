/** [longitude, latitude], the order MapLibre and GeoJSON use. */
export type LngLat = [number, number];

/** University Centre, Fort Garry campus. Matches CAMPUS in the Trips service. */
export const CAMPUS: LngLat = [-97.1366, 49.8075];

/** A view that shows most of Winnipeg south of downtown, campus included. */
export const WINNIPEG_VIEW = { longitude: -97.145, latitude: 49.845, zoom: 12 } as const;

const EARTH_RADIUS_METERS = 6_371_000;

/**
 * A circle as a closed polygon ring, for drawing "your area". MapLibre has no
 * geographic circle, so this approximates one with `steps` points.
 */
export function circlePolygon(center: LngLat, radiusMeters: number, steps = 64): LngLat[] {
  const [lng, lat] = center;
  const latRad = (lat * Math.PI) / 180;
  const dLat = (radiusMeters / EARTH_RADIUS_METERS) * (180 / Math.PI);
  const dLng = dLat / Math.cos(latRad);

  const ring: LngLat[] = [];
  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    ring.push([lng + dLng * Math.cos(angle), lat + dLat * Math.sin(angle)]);
  }
  ring.push(ring[0]!);
  return ring;
}

/** The smallest box containing every point: [[west, south], [east, north]]. */
export function boundsOf(points: LngLat[]): [LngLat, LngLat] {
  if (points.length === 0) {
    throw new Error("boundsOf needs at least one point");
  }
  const lngs = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}
