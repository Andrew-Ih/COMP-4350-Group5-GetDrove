import { CAMPUS, type LngLat, type MapMarker, type MapRoute } from "@/shared/map";

// A sample trip for the design pages: Wolseley → Osborne Village → Pembina → campus.
// Approximate, for display only.
const start: LngLat = [-97.1745, 49.8786];
const pickup: LngLat = [-97.1445, 49.8786];
const you: LngLat = [-97.1405, 49.8762];
const toCampus: LngLat[] = [
  pickup,
  [-97.1452, 49.8622],
  [-97.1473, 49.858],
  [-97.15, 49.842],
  [-97.152, 49.83],
  [-97.151, 49.82],
  [-97.144, 49.813],
  CAMPUS,
];

export const sampleRoutes: MapRoute[] = [
  { id: "hidden-start", coordinates: [start, [-97.16, 49.8786], pickup], style: "hidden" },
  { id: "trip", coordinates: toCampus, style: "primary" },
  { id: "walk", coordinates: [you, [-97.1405, 49.8786], pickup], style: "walk" },
];

export const sampleMarkers: MapMarker[] = [
  { id: "pickup", lngLat: pickup, kind: "pickup", label: "Pickup · 7:48 AM" },
  { id: "you", lngLat: you, kind: "you", label: "You" },
  { id: "campus", lngLat: CAMPUS, kind: "campus", label: "University Centre" },
];

export const sampleArea = { center: you, radiusMeters: 450 };
