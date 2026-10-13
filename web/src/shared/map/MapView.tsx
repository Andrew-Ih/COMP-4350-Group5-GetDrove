"use client";

import dynamic from "next/dynamic";

/**
 * The map (MapLibre + OpenFreeMap, ADR 0009). MapLibre only works in the browser, so it's
 * loaded on the client only, with a plain background while it loads.
 *
 *   <MapView
 *     routes={[{ id: "trip", coordinates: [...], style: "primary" }]}
 *     markers={[{ id: "pickup", lngLat: [-97.14, 49.87], kind: "pickup" }]}
 *     area={{ center: [-97.14, 49.87], radiusMeters: 400 }}
 *   />
 *
 * The map zooms to fit everything it's given.
 */
export const MapView = dynamic(() => import("./MapView.client"), {
  ssr: false,
  loading: () => <div className="size-full bg-map-land" />,
});
