"use client";

import { ArrowRight, Clock, LocateFixed } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, MapView, WINNIPEG_VIEW } from "@/shared/map";
import { AppHeader, Button, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { type PositionError, useCurrentPosition } from "../hooks/useCurrentPosition";
import {
  AREA_RADIUS_METERS,
  areaName,
  defaultWhen,
  type Direction,
  isInServiceArea,
  today,
  toQueryString,
  toSearchTime,
  WHEN_LABEL,
} from "../model/search";

const CAMPUS_NAME = "U of M Fort Garry Campus";

const POSITION_ERRORS: Record<PositionError, string> = {
  denied: "Location is turned off for this site. Tap the map to choose your area instead.",
  unavailable: "We couldn't find your location. Tap the map to choose your area instead.",
  unsupported: "This browser can't share your location. Tap the map to choose your area instead.",
};

function greeting(now: Date = new Date()): string {
  const hour = now.getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

/**
 * The rider home (#98): choose an area on the map, a direction and a time, then search.
 * Collects exactly what GET /api/trips/search needs: lat, lng, direction and time.
 */
export function RideHome() {
  const router = useRouter();
  const me = useCurrentUser();

  const [point, setPoint] = useState<LngLat>();
  const [focus, setFocus] = useState<LngLat>();
  const [direction, setDirection] = useState<Direction>("to_campus");
  const [when, setWhen] = useState(() => defaultWhen("to_campus"));
  const [error, setError] = useState<string>();

  const choose = useCallback((picked: LngLat, moveMap: boolean) => {
    if (!isInServiceArea(picked)) {
      setError("GetDrove only covers Winnipeg for now. Choose an area closer to campus.");
      return;
    }
    setError(undefined);
    setPoint(picked);
    if (moveMap) setFocus(picked);
  }, []);

  const position = useCurrentPosition(useCallback((p: LngLat) => choose(p, true), [choose]));

  const area = point ? (areaName(point) ?? "Your chosen area") : undefined;
  const yourAreaLabel = direction === "to_campus" ? "Pickup area" : "Drop-off area";

  const markers = useMemo<MapMarker[]>(() => {
    const list: MapMarker[] = [{ id: "campus", lngLat: CAMPUS, kind: "campus", label: "U of M Fort Garry" }];
    if (point) list.push({ id: "you", lngLat: point, kind: "you", label: area });
    return list;
  }, [point, area]);

  function switchDirection(next: Direction) {
    if (next === direction) return;
    setDirection(next);
    // Keep the date the rider picked, but use the typical time for the new direction.
    setWhen((current) => ({ date: current.date, time: defaultWhen(next).time }));
  }

  function findRides() {
    if (!point) {
      setError("Tap the map or use your location to choose your area.");
      return;
    }
    const time = toSearchTime(when.date, when.time);
    if (!time) {
      setError("Choose a date and time.");
      return;
    }
    if (Date.parse(time) <= Date.now()) {
      setError("Choose a time in the future.");
      return;
    }
    router.push(`/ride/results?${toQueryString({ lat: point[1], lng: point[0], direction, time })}`);
  }

  const yourAreaRow = (
    <div className="flex items-center gap-4 py-3">
      <span aria-hidden="true" className="size-3 shrink-0 rounded-full bg-ink" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-ink-soft">{yourAreaLabel}</p>
        <p className={cn("truncate text-lg font-bold", !area && "text-subtle")}>
          {area ?? "Tap the map or use your location"}
        </p>
      </div>
      <button
        type="button"
        onClick={position.request}
        aria-label="Use my location"
        className="flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-line"
      >
        {position.locating ? <Spinner className="size-5" /> : <LocateFixed className="size-5" />}
      </button>
    </div>
  );

  const campusRow = (
    <div className="flex items-center gap-4 py-3">
      <span aria-hidden="true" className="size-3 shrink-0 bg-ink" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-ink-soft">{direction === "to_campus" ? "Destination" : "Leaving from"}</p>
        <p className="truncate text-lg font-bold">{CAMPUS_NAME}</p>
      </div>
    </div>
  );

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <MapLayout
        map={
          <MapView
            initialView={WINNIPEG_VIEW}
            markers={markers}
            area={point ? { center: point, radiusMeters: AREA_RADIUS_METERS } : undefined}
            focus={focus}
            onPick={(picked) => choose(picked, false)}
            onLocate={position.request}
          />
        }
        panel={
          <>
            <p className="text-lg text-ink-soft">
              {greeting()}
              {me.data ? `, ${me.data.firstName}` : ""}
            </p>
            <h1 className="mt-1 text-3xl leading-tight md:text-4xl">Where are you heading?</h1>

            <div role="radiogroup" aria-label="Direction" className="mt-6 grid grid-cols-2 gap-1 rounded-md bg-surface-muted p-1">
              {(["to_campus", "from_campus"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={direction === option}
                  onClick={() => switchDirection(option)}
                  className={cn(
                    "h-10 rounded-sm font-bold transition-colors",
                    direction === option ? "bg-ink text-white" : "text-ink-soft hover:text-ink",
                  )}
                >
                  {option === "to_campus" ? "To campus" : "From campus"}
                </button>
              ))}
            </div>

            <div className="mt-4 rounded-lg bg-surface-muted px-5">
              {direction === "to_campus" ? yourAreaRow : campusRow}
              <div className="ml-7 border-t border-line" />
              {direction === "to_campus" ? campusRow : yourAreaRow}
            </div>

            <fieldset className="mt-4 rounded-lg bg-surface-muted px-5 py-3">
              <legend className="sr-only">When</legend>
              <div className="flex items-center gap-4">
                <Clock aria-hidden="true" className="size-5 shrink-0" />
                <div className="grid min-w-0 flex-1 grid-cols-[1fr_auto] gap-x-3">
                  <span className="col-span-2 text-sm font-semibold text-ink-soft">{WHEN_LABEL[direction]}</span>
                  <label className="sr-only" htmlFor="ride-date">
                    Date
                  </label>
                  <input
                    id="ride-date"
                    type="date"
                    min={today()}
                    value={when.date}
                    onChange={(event) => setWhen((current) => ({ ...current, date: event.target.value }))}
                    className="min-w-0 bg-transparent text-lg font-bold outline-none"
                  />
                  <label className="sr-only" htmlFor="ride-time">
                    {WHEN_LABEL[direction]}
                  </label>
                  <input
                    id="ride-time"
                    type="time"
                    step={300}
                    value={when.time}
                    onChange={(event) => setWhen((current) => ({ ...current, time: event.target.value }))}
                    className="bg-transparent text-lg font-bold outline-none"
                  />
                </div>
              </div>
            </fieldset>

            <p role="alert" className="mt-3 min-h-5 text-sm font-semibold text-danger">
              {error ?? (position.error ? POSITION_ERRORS[position.error] : "")}
            </p>

            <Button fullWidth size="md" className="mt-1" onClick={findRides} disabled={!point}>
              Find rides <ArrowRight className="size-5" />
            </Button>

            <PrivacyNote className="mt-6">
              Only your general area is used. You&apos;ll meet drivers at a pickup point on their route.
            </PrivacyNote>
          </>
        }
      />
    </>
  );
}
