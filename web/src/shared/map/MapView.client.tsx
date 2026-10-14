"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { LocateFixed, Minus, Plus } from "lucide-react";
import type { LineLayerSpecification, Map as MapLibreMap } from "maplibre-gl";
import { type ReactNode, useCallback, useMemo, useRef } from "react";
import Map, { Layer, Marker, type MapRef, Source } from "react-map-gl/maplibre";

import { cn } from "@/shared/lib/cn";

import { mapColors } from "./colors";
import { boundsOf, circlePolygon, type LngLat, WINNIPEG_VIEW } from "./geo";
import type { MapMarker, MapRoute, MapViewProps } from "./types";

// Free vector tiles, no API key (ADR 0009). Recoloured below to match the mockups.
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

const ROUTE_PAINT: Record<MapRoute["style"], LineLayerSpecification["paint"]> = {
  primary: { "line-color": mapColors.brand, "line-width": 6 },
  light: { "line-color": mapColors.brandLight, "line-width": 6 },
  other: { "line-color": mapColors.otherRoute, "line-width": 5 },
  hidden: { "line-color": mapColors.brand, "line-width": 4, "line-dasharray": [1, 1.5] },
  walk: { "line-color": mapColors.ink, "line-width": 3, "line-dasharray": [0.5, 1.5] },
};

/** Recolours OpenFreeMap's Positron style with our land, water and park colours. */
function applyTheme(map: MapLibreMap) {
  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id.toLowerCase();
    if (layer.type === "background") {
      map.setPaintProperty(layer.id, "background-color", mapColors.land);
    } else if (layer.type === "fill" && id.includes("water")) {
      map.setPaintProperty(layer.id, "fill-color", mapColors.water);
    } else if (layer.type === "line" && id.includes("water")) {
      map.setPaintProperty(layer.id, "line-color", mapColors.water);
    } else if (layer.type === "fill" && /park|wood|grass|landcover/.test(id)) {
      map.setPaintProperty(layer.id, "fill-color", mapColors.park);
    }
  }
}

export default function MapView({ routes = [], markers = [], area, fitPadding = 60, className }: MapViewProps) {
  const mapRef = useRef<MapRef>(null);

  const allPoints = useMemo<LngLat[]>(
    () => [...routes.flatMap((r) => r.coordinates), ...markers.map((m) => m.lngLat), ...(area ? [area.center] : [])],
    [routes, markers, area],
  );

  const onLoad = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    applyTheme(map);
    if (allPoints.length > 1) {
      map.fitBounds(boundsOf(allPoints), { padding: fitPadding, duration: 0 });
    }
  }, [allPoints, fitPadding]);

  const locate = () => {
    navigator.geolocation?.getCurrentPosition((pos) => {
      mapRef.current?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 14 });
    });
  };

  const initialView =
    allPoints.length === 1 ? { longitude: allPoints[0]![0], latitude: allPoints[0]![1], zoom: 14 } : WINNIPEG_VIEW;

  return (
    <div className={cn("relative size-full bg-map-land", className)}>
      <Map
        ref={mapRef}
        initialViewState={initialView}
        mapStyle={STYLE_URL}
        onLoad={onLoad}
        attributionControl={{ compact: true }}
        style={{ width: "100%", height: "100%" }}
      >
        {area && (
          <Source
            id="area"
            type="geojson"
            data={{
              type: "Feature",
              properties: {},
              geometry: { type: "Polygon", coordinates: [circlePolygon(area.center, area.radiusMeters)] },
            }}
          >
            <Layer id="area-fill" type="fill" paint={{ "fill-color": mapColors.brandSoft, "fill-opacity": 0.7 }} />
            <Layer
              id="area-line"
              type="line"
              paint={{ "line-color": mapColors.brand, "line-width": 2, "line-dasharray": [2, 2] }}
            />
          </Source>
        )}

        {routes.map((route) => (
          <Source
            key={route.id}
            id={`route-${route.id}`}
            type="geojson"
            data={{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: route.coordinates } }}
          >
            <Layer
              id={`route-${route.id}`}
              type="line"
              layout={{ "line-cap": "round", "line-join": "round" }}
              paint={ROUTE_PAINT[route.style]}
            />
          </Source>
        ))}

        {markers.map((marker) => (
          <Marker key={marker.id} longitude={marker.lngLat[0]} latitude={marker.lngLat[1]} anchor={marker.kind === "pickup" ? "bottom" : "center"}>
            <MarkerIcon kind={marker.kind} label={marker.label} />
          </Marker>
        ))}
      </Map>

      {/* Zoom and locate buttons on desktop only; on phones the mockups use pinch-to-zoom. */}
      <div className="absolute top-4 right-4 hidden flex-col gap-3 md:flex">
        <div className="flex flex-col overflow-hidden rounded-md bg-surface shadow-card">
          <MapButton label="Zoom in" onClick={() => mapRef.current?.zoomIn()}>
            <Plus className="size-5" />
          </MapButton>
          <div className="h-px bg-line" />
          <MapButton label="Zoom out" onClick={() => mapRef.current?.zoomOut()}>
            <Minus className="size-5" />
          </MapButton>
        </div>
        <div className="overflow-hidden rounded-md bg-surface shadow-card">
          <MapButton label="Show my location" onClick={locate}>
            <LocateFixed className="size-5" />
          </MapButton>
        </div>
      </div>
    </div>
  );
}

function MapButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-label={label} onClick={onClick} className="flex size-12 items-center justify-center hover:bg-surface-muted">
      {children}
    </button>
  );
}

function MarkerIcon({ kind, label }: Pick<MapMarker, "kind" | "label">) {
  const shape = {
    // Black map pin: the pickup point.
    pickup: (
      <svg width="34" height="44" viewBox="0 0 34 44" aria-hidden="true">
        <path d="M17 0C7.6 0 0 7.5 0 16.8 0 29.4 17 44 17 44s17-14.6 17-27.2C34 7.5 26.4 0 17 0z" fill={mapColors.ink} />
        <circle cx="17" cy="16.5" r="6.5" fill="#fff" />
      </svg>
    ),
    // Black square with a white centre: campus or the drop-off.
    campus: <span className="flex size-7 items-center justify-center bg-ink"><span className="size-2.5 bg-white" /></span>,
    // Black dot with a grey ring: the rider ("You").
    you: <span className="block size-6 rounded-full border-[5px] border-[#c9cbc7] bg-ink" />,
    // White circle with a black border: another stop on a route.
    stop: <span className="block size-6 rounded-full border-[5px] border-ink bg-white" />,
  }[kind];

  // The label sits beside the shape without moving it, so the shape stays exactly on the point.
  return (
    <div className="relative">
      {shape}
      {label && (
        <span className="absolute top-1/2 left-full ml-2 -translate-y-1/2 rounded-sm bg-surface px-2.5 py-1 text-sm font-bold whitespace-nowrap shadow-card">
          {label}
        </span>
      )}
    </div>
  );
}
