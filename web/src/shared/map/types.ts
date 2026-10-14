import type { LngLat } from "./geo";

export type MapRoute = {
  id: string;
  coordinates: LngLat[];
  /**
   * primary: the selected or driver's route (green) · light: the rest of a route (light green)
   * · other: other trips (grey) · hidden: a part riders can't see (dashed) · walk: a walk to a pickup (dotted)
   */
  style: "primary" | "light" | "other" | "hidden" | "walk";
};

export type MapMarker = {
  id: string;
  lngLat: LngLat;
  kind: "pickup" | "campus" | "you" | "stop";
  /** Short text shown next to the marker, e.g. "Jordan 8:01". */
  label?: string;
};

export type MapViewProps = {
  routes?: MapRoute[];
  markers?: MapMarker[];
  /** The rider's or driver's private area, drawn as a dashed green circle. */
  area?: { center: LngLat; radiusMeters: number };
  /** Space in pixels kept around everything when the map zooms to fit it. */
  fitPadding?: number;
  className?: string;
};
