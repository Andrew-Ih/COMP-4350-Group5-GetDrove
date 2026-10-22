"use client";

import { CalendarDays, CheckCircle2, Clock, LocateFixed, Lock } from "lucide-react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import {
  AREA_RADIUS_METERS,
  type Direction,
  isInServiceArea,
  type PositionError,
  today,
  useCurrentPosition,
} from "@/features/ride";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, type MapRoute, MapView, WINNIPEG_VIEW } from "@/shared/map";
import { AppHeader, Button, buttonStyles, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { useMyDrivingTrips, usePostTrip, useTripRoute } from "../hooks/usePostTrip";
import {
  buildPostTrip,
  DEFAULT_SEATS,
  defaultDeparture,
  ENDS,
  findOverlap,
  formatClock,
  formatDay,
  formatDistance,
  formatDuration,
  type FormProblem,
  overlapMessage,
  placeLabel,
  SEAT_OPTIONS,
  type Trip,
} from "../model/postTrip";

const CAMPUS_NAME = "U of M Fort Garry Campus";

const POSITION_ERRORS: Record<PositionError, string> = {
  denied: "Location is turned off for this site. Tap the map to choose your area instead.",
  unavailable: "We couldn't find your location. Tap the map to choose your area instead.",
  unsupported: "This browser can't share your location. Tap the map to choose your area instead.",
};

/** What went wrong when posting, in words, keyed on the contract's error codes. */
function postProblem(error: ApiError): FormProblem | { field: "session"; message: string } {
  const departure = error.problem.errors?.find((e) => e.field === "departureAt");
  if (error.code === "departure_in_past" || departure) {
    return { field: "departure", message: "Choose a departure time in the future." };
  }
  if (error.problem.errors?.some((e) => e.field === "seatsTotal")) {
    return { field: "seats", message: "Offer between 1 and 6 seats." };
  }
  if (error.code === "routing_unavailable" || error.code === "service_unavailable") {
    return {
      field: "place",
      message: "We couldn't work out your route right now, so the trip wasn't posted. Try again in a minute.",
    };
  }
  if (error.code === "unauthorized") {
    return { field: "session", message: "Your session has ended. Log in again to post your trip." };
  }
  return { field: "place", message: error.message };
}

/**
 * Post a one-off trip to or from campus (#96), with POST /api/trips/. The driver's end is
 * chosen on the map and saved as a neighbourhood label ("Wolseley area"), never an address.
 * The route is worked out when the trip is posted, so the estimate is shown afterwards.
 */
export function PostTrip() {
  const me = useCurrentUser();
  const post = usePostTrip();
  const myDrivingTrips = useMyDrivingTrips();
  const [checking, setChecking] = useState(false);

  const [direction, setDirection] = useState<Direction>("to_campus");
  const [point, setPoint] = useState<LngLat>();
  const [focus, setFocus] = useState<LngLat>();
  const [when, setWhen] = useState(() => defaultDeparture("to_campus"));
  const [seats, setSeats] = useState(DEFAULT_SEATS);
  const [problem, setProblem] = useState<FormProblem | { field: "session"; message: string }>();

  const choose = useCallback((picked: LngLat, moveMap: boolean) => {
    if (!isInServiceArea(picked)) {
      setProblem({ field: "place", message: "GetDrove only covers Winnipeg for now. Choose a spot closer to campus." });
      return;
    }
    setProblem(undefined);
    setPoint(picked);
    if (moveMap) setFocus(picked);
  }, []);
  const position = useCurrentPosition(useCallback((p: LngLat) => choose(p, true), [choose]));

  function switchDirection(next: Direction) {
    if (next === direction) return;
    setDirection(next);
    setWhen((current) => ({ date: current.date, time: defaultDeparture(next).time }));
  }

  async function submit() {
    const built = buildPostTrip({ direction, point, date: when.date, time: when.time, seats });
    if ("problem" in built) {
      setProblem(built.problem);
      return;
    }
    setProblem(undefined);

    // Warn before posting a trip that clashes with one already posted.
    setChecking(true);
    const mine = await myDrivingTrips();
    setChecking(false);
    const clash = mine && findOverlap(mine, built.body.departureAt);
    if (clash) {
      setProblem({ field: "departure", message: overlapMessage(clash) });
      return;
    }

    post.mutate(built.body, { onError: (error) => setProblem(postProblem(error)) });
  }

  function postAnother() {
    post.reset();
    setProblem(undefined);
  }

  const posted = post.data;
  const route = useTripRoute(posted?.id);

  const markers = useMemo<MapMarker[]>(() => {
    const list: MapMarker[] = [{ id: "campus", lngLat: CAMPUS, kind: "campus", label: "U of M Fort Garry" }];
    if (point) list.push({ id: "place", lngLat: point, kind: "you", label: placeLabel(point) });
    return list;
  }, [point]);

  const routes = useMemo<MapRoute[]>(
    () => (route.data ? [{ id: "route", coordinates: route.data.geometry.coordinates as LngLat[], style: "primary" }] : []),
    [route.data],
  );

  const map = posted ? (
    // A fresh map for the posted trip, fitted to its two ends; the route is drawn as it arrives.
    <MapView key={posted.id} markers={markers} routes={routes} />
  ) : (
    <MapView
      initialView={WINNIPEG_VIEW}
      markers={markers}
      area={point ? { center: point, radiusMeters: AREA_RADIUS_METERS } : undefined}
      focus={focus}
      onPick={(picked) => choose(picked, false)}
      onLocate={position.request}
    />
  );

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <MapLayout
        map={map}
        panel={
          posted && point ? (
            <Posted trip={posted} place={placeLabel(point)} onPostAnother={postAnother} />
          ) : (
            <>
              <h1 className="text-3xl leading-tight md:text-4xl">Post a trip</h1>

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

              <Ends
                direction={direction}
                place={point ? placeLabel(point) : undefined}
                locating={position.locating}
                onLocate={position.request}
              />

              <fieldset className="mt-4 grid grid-cols-2 gap-3">
                <legend className="sr-only">When you leave</legend>
                <label className="flex items-center gap-3 rounded-lg bg-surface-muted px-4 py-3">
                  <CalendarDays aria-hidden="true" className="size-5 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-ink-soft">Date</span>
                    <input
                      type="date"
                      min={today()}
                      value={when.date}
                      onChange={(event) => setWhen((current) => ({ ...current, date: event.target.value }))}
                      className="w-full min-w-0 bg-transparent text-lg font-bold outline-none"
                    />
                  </span>
                </label>
                <label className="flex items-center gap-3 rounded-lg bg-surface-muted px-4 py-3">
                  <Clock aria-hidden="true" className="size-5 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-ink-soft">Departure time</span>
                    <input
                      type="time"
                      step={300}
                      value={when.time}
                      onChange={(event) => setWhen((current) => ({ ...current, time: event.target.value }))}
                      className="w-full min-w-0 bg-transparent text-lg font-bold outline-none"
                    />
                  </span>
                </label>
              </fieldset>

              <p id="seats-label" className="mt-6 font-bold">
                Seats for riders
              </p>
              <div role="radiogroup" aria-labelledby="seats-label" className="mt-2 grid grid-cols-6 gap-2">
                {SEAT_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    role="radio"
                    aria-checked={seats === option}
                    onClick={() => setSeats(option)}
                    className={cn(
                      "h-12 rounded-md border-2 text-lg font-bold transition-colors",
                      seats === option ? "border-ink bg-ink text-white" : "border-line hover:border-line-strong",
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>

              <div role="alert" className="mt-4 min-h-5 text-sm font-semibold text-danger">
                {problem?.message ?? (position.error ? POSITION_ERRORS[position.error] : "")}
                {problem?.field === "session" && (
                  <Link href="/login?next=%2Fdrive%2Fnew" className="ml-1 underline">
                    Log in
                  </Link>
                )}
              </div>

              <Button fullWidth className="mt-2" onClick={() => void submit()} loading={checking || post.isPending} disabled={!point}>
                {checking || post.isPending ? "Posting…" : "Post trip"}
              </Button>

              <PrivacyNote className="mt-4">
                Riders never see the name or address of your area. They find your trip when it passes near them.
              </PrivacyNote>
            </>
          )
        }
      />
    </>
  );
}

function Ends({
  direction,
  place,
  locating,
  onLocate,
}: {
  direction: Direction;
  place: string | undefined;
  locating: boolean;
  onLocate: () => void;
}) {
  const placeRow = (
    <div className="flex items-center gap-4 py-3">
      <span aria-hidden="true" className="size-3 shrink-0 rounded-full bg-ink" />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink-soft">
          {ENDS[direction].place}
          <span className="inline-flex items-center gap-1 text-xs">
            <Lock aria-hidden="true" className="size-3" /> Private
          </span>
        </p>
        <p className={cn("truncate text-lg font-bold", !place && "text-subtle")}>{place ?? "Tap the map or use your location"}</p>
      </div>
      <button
        type="button"
        onClick={onLocate}
        aria-label="Use my location"
        className="flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-line"
      >
        {locating ? <Spinner className="size-5" /> : <LocateFixed className="size-5" />}
      </button>
    </div>
  );
  const campusRow = (
    <div className="flex items-center gap-4 py-3">
      <span aria-hidden="true" className="size-3 shrink-0 bg-ink" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-ink-soft">{ENDS[direction].campus}</p>
        <p className="truncate text-lg font-bold">{CAMPUS_NAME}</p>
      </div>
    </div>
  );
  return (
    <div className="mt-4 rounded-lg bg-surface-muted px-5">
      {direction === "to_campus" ? placeRow : campusRow}
      <div className="ml-7 border-t border-line" />
      {direction === "to_campus" ? campusRow : placeRow}
    </div>
  );
}

function Posted({ trip, place, onPostAnother }: { trip: Trip; place: string; onPostAnother: () => void }) {
  const from = trip.direction === "to_campus" ? place : CAMPUS_NAME;
  const to = trip.direction === "to_campus" ? CAMPUS_NAME : place;
  return (
    <div role="status">
      <p className="flex items-center gap-2 font-bold text-brand">
        <CheckCircle2 aria-hidden="true" className="size-5" /> Trip posted
      </p>
      <h1 className="mt-2 text-3xl leading-tight md:text-4xl">
        {formatDay(trip.departureAt)}, {formatClock(trip.departureAt)}
      </h1>

      <dl className="mt-6 space-y-3 rounded-lg bg-surface-muted p-5">
        <Row term="Route" value={`${from} → ${to}`} />
        <Row term="Departs" value={formatClock(trip.departureAt)} />
        <Row term="Arrives about" value={formatClock(trip.estimatedArrivalAt)} />
        <Row term="Driving" value={`${formatDuration(trip.durationSeconds)} · ${formatDistance(trip.distanceMeters)}`} />
        <Row term="Seats for riders" value={String(trip.seatsTotal)} />
      </dl>

      <p className="mt-4 text-ink-soft">Riders whose area is along your route can now find this trip when they search.</p>

      <div className="mt-6 flex flex-col gap-3">
        <Button fullWidth onClick={onPostAnother}>
          Post another trip
        </Button>
        <Link href="/ride" className={buttonStyles({ variant: "secondary", fullWidth: true })}>
          Find a ride instead
        </Link>
      </div>
    </div>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-ink-soft">{term}</dt>
      <dd className="text-right font-bold">{value}</dd>
    </div>
  );
}
