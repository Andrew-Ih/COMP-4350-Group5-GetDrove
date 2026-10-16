"use client";

import { useCallback, useState } from "react";

import type { LngLat } from "@/shared/map";

export type PositionError = "denied" | "unavailable" | "unsupported";

/**
 * Asks the browser for the device's location, once, when `request()` is called (never on
 * page load). The browser shows its own permission prompt.
 */
export function useCurrentPosition(onPosition: (point: LngLat) => void) {
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<PositionError>();

  const request = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setError("unsupported");
      return;
    }
    setLocating(true);
    setError(undefined);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        onPosition([position.coords.longitude, position.coords.latitude]);
      },
      (failure) => {
        setLocating(false);
        setError(failure.code === failure.PERMISSION_DENIED ? "denied" : "unavailable");
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  }, [onPosition]);

  return { request, locating, error };
}
