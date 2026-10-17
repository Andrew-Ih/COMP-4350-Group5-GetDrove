"use client";

import { ArrowLeft, ArrowUpDown, Car, Footprints } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, type MapRoute, MapView } from "@/shared/map";
import { AppHeader, Button, buttonStyles, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { useRoutes, useTripSearch } from "../hooks/useTripSearch";
import {
  formatClock,
  formatMoney,
  formatWalk,
  resultsHeading,
  routeCoordinates,
  searchSummary,
  seatsLeft,
  SORT_LABEL,
  type SearchResult,
  type SortBy,
  sortResults,
} from "../model/results";
import { AREA_RADIUS_METERS, type SearchQuery, toQueryString } from "../model/search";

/**
 * Search results (#27) with the rider's share on each trip (#100), from GET /api/trips/search.
 * The selected trip's route comes from Routing. `query` is undefined when the URL is
 * missing a field or has a wrong one.
 */
export function TripResults({ query }: { query: SearchQuery | undefined }) {
  const me = useCurrentUser();
  const search = useTripSearch(query);
  const [sortBy, setSortBy] = useState<SortBy>("departure");
  const [chosenId, setChosenId] = useState<string>();

  const results = useMemo(() => sortResults(search.data ?? [], sortBy), [search.data, sortBy]);
  // The rider's choice, or the first trip in the list until they choose one.
  const selected = results.find((r) => r.trip.id === chosenId) ?? results[0];
  // In the API's order (soonest first), so sorting the list doesn't refetch or reorder the map.
  const tripIds = useMemo(() => (search.data ?? []).map((r) => r.trip.id), [search.data]);
  const routes = useRoutes(tripIds);

  // Memoised: the map re-fits whenever what it shows changes, so this must stay the same object.
  const you = useMemo<LngLat | undefined>(() => (query ? [query.lng, query.lat] : undefined), [query]);
  const area = useMemo(() => (you ? { center: you, radiusMeters: AREA_RADIUS_METERS } : undefined), [you]);

  const markers = useMemo<MapMarker[]>(() => {
    const list: MapMarker[] = [{ id: "campus", lngLat: CAMPUS, kind: "campus", label: "U of M Fort Garry" }];
    for (const result of results) {
      if (result === selected) continue;
      list.push({
        id: `pickup-${result.trip.id}`,
        lngLat: [result.pickup.lng, result.pickup.lat],
        kind: "stop",
        label: formatClock(result.trip.departureAt),
      });
    }
    if (selected) {
      list.push({ id: "pickup", lngLat: [selected.pickup.lng, selected.pickup.lat], kind: "pickup", label: selected.pickup.label });
    }
    if (you) list.push({ id: "you", lngLat: you, kind: "you", label: "You" });
    return list;
  }, [results, selected, you]);

  const mapRoutes = useMemo<MapRoute[]>(() => {
    // Other trips in grey first, so the selected one (green) is drawn on top.
    const list: MapRoute[] = [];
    for (const [tripId, route] of routes) {
      if (tripId !== selected?.trip.id) list.push({ id: `other-${tripId}`, coordinates: routeCoordinates(route), style: "other" });
    }
    const selectedRoute = selected && routes.get(selected.trip.id);
    if (selectedRoute) list.push({ id: "selected", coordinates: routeCoordinates(selectedRoute), style: "primary" });
    if (selected && you) {
      // A straight dotted line to the pickup point, like the mockup: not the exact walking path.
      list.push({ id: "walk", coordinates: [you, [selected.pickup.lng, selected.pickup.lat]], style: "walk" });
    }
    return list;
  }, [routes, selected, you]);

  // Fit the rider, campus and every pickup once per set of results. Choosing a trip or a
  // route loading doesn't move the map, so it stays still while the rider compares trips.
  const fitTo = useMemo(() => {
    if (!you) return undefined;
    const results = search.data ?? [];
    return {
      key: results.map((r) => r.trip.id).join(",") || "no-results",
      points: [you, CAMPUS, ...results.map((r): LngLat => [r.pickup.lng, r.pickup.lat])],
    };
  }, [you, search.data]);

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <MapLayout
        map={<MapView routes={mapRoutes} markers={markers} area={area} fitTo={fitTo} />}
        panel={
          query ? (
            <Results
              query={query}
              status={search.status}
              error={search.error}
              onRetry={() => void search.refetch()}
              results={results}
              selected={selected}
              onSelect={setChosenId}
              sortBy={sortBy}
              onSort={setSortBy}
            />
          ) : (
            <Message title="This search link is incomplete">
              <p>Choose your area, direction and time again to see trips.</p>
              <Link href="/ride" className={buttonStyles({ size: "md", fullWidth: true })}>
                Start a new search
              </Link>
            </Message>
          )
        }
      />
    </>
  );
}

type ResultsProps = {
  query: SearchQuery;
  status: "pending" | "error" | "success";
  error: ApiError | null;
  onRetry: () => void;
  results: SearchResult[];
  selected: SearchResult | undefined;
  onSelect: (tripId: string) => void;
  sortBy: SortBy;
  onSort: (by: SortBy) => void;
};

function Results({ query, status, error, onRetry, results, selected, onSelect, sortBy, onSort }: ResultsProps) {
  const summary = searchSummary(query);
  const changeSearch = `/ride?${toQueryString(query)}`;

  return (
    <>
      <div className="flex items-center gap-3">
        <Link
          href={changeSearch}
          aria-label="Change search"
          className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface-muted hover:bg-line"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <div className="min-w-0 flex-1 rounded-md bg-surface-muted px-4 py-2.5">
          <p className="truncate font-bold">{summary.route}</p>
          <p className="truncate text-sm text-ink-soft">{summary.when}</p>
        </div>
      </div>

      {status === "pending" && (
        <p className="mt-10 flex items-center justify-center gap-3 font-semibold text-ink-soft" role="status">
          <Spinner className="size-5" /> Finding trips near you…
        </p>
      )}

      {status === "error" && <SearchError error={error} onRetry={onRetry} changeSearch={changeSearch} />}

      {status === "success" && (
        <>
          <div className="mt-6 flex items-center justify-between gap-3">
            <h1 className="text-2xl leading-tight md:text-3xl">{resultsHeading(results.length, query)}</h1>
            {results.length > 1 && <SortControl value={sortBy} onChange={onSort} />}
          </div>

          {results.length === 0 ? (
            <div className="mt-3 space-y-5 text-ink-soft">
              <p>
                No driver&apos;s route passes within walking distance of your area at that time. Try a different time,
                or a spot closer to a main road.
              </p>
              <Link href={changeSearch} className={buttonStyles({ size: "md", fullWidth: true })}>
                Change search
              </Link>
            </div>
          ) : (
            <>
              <div role="radiogroup" aria-label="Trips" className="mt-4 space-y-3">
                {results.map((result) => (
                  <ResultCard
                    key={result.trip.id}
                    result={result}
                    direction={query.direction}
                    selected={result === selected}
                    onSelect={() => onSelect(result.trip.id)}
                  />
                ))}
              </div>
              {selected && (
                <p className="mt-4 text-sm text-ink-soft">
                  Pickup at <span className="font-semibold text-ink">{selected.pickup.label}</span>
                  {selected.cost ? ` · your share: ${selected.cost.explanation}` : ""}
                </p>
              )}
            </>
          )}
        </>
      )}

      <PrivacyNote className="mt-6">
        Your location is only used to find trips. It&apos;s never saved or shown to drivers.
      </PrivacyNote>
    </>
  );
}

function ResultCard({
  result,
  direction,
  selected,
  onSelect,
}: {
  result: SearchResult;
  direction: SearchQuery["direction"];
  selected: boolean;
  onSelect: () => void;
}) {
  const { trip, pickup, cost } = result;
  const departs = `Departs ${formatClock(trip.departureAt)}`;
  const arrives = direction === "to_campus" ? `Arrives ${formatClock(trip.estimatedArrivalAt)}` : undefined;

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={`${departs}, ${cost ? `${formatMoney(cost.amountCents)} your share` : "price unavailable"}`}
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-4 rounded-lg border-2 bg-surface p-4 text-left transition-colors",
        selected ? "border-ink" : "border-line hover:border-line-strong",
      )}
    >
      <span aria-hidden="true" className="flex size-12 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
        <Car className="size-6" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-lg font-bold">{departs}</span>
        <span className="block text-ink-soft">{[arrives, seatsLeft(trip.seatsAvailable)].filter(Boolean).join(" · ")}</span>
        <span className="mt-0.5 flex items-center gap-1.5 text-ink-soft">
          <Footprints aria-hidden="true" className={cn("size-4 shrink-0", selected && "text-brand")} />
          <span className="truncate">
            {formatWalk(pickup.walkSeconds)} to {pickup.label}
          </span>
        </span>
      </span>
      <span className="shrink-0 text-right">
        {cost ? (
          <>
            <span className="block text-2xl font-extrabold">{formatMoney(cost.amountCents)}</span>
            <span className="block text-sm text-ink-soft">your share</span>
          </>
        ) : (
          <span className="block max-w-20 text-sm font-semibold text-ink-soft">Price unavailable</span>
        )}
      </span>
    </button>
  );
}

function SortControl({ value, onChange }: { value: SortBy; onChange: (by: SortBy) => void }) {
  return (
    <label className="relative flex h-11 shrink-0 items-center gap-2 rounded-full border-2 border-line px-4 font-bold hover:border-line-strong">
      <ArrowUpDown aria-hidden="true" className="size-4" />
      <span className="sr-only">Sort by</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as SortBy)}
        className="cursor-pointer appearance-none bg-transparent outline-none"
      >
        {(Object.keys(SORT_LABEL) as SortBy[]).map((by) => (
          <option key={by} value={by}>
            {SORT_LABEL[by]}
          </option>
        ))}
      </select>
    </label>
  );
}

function SearchError({ error, onRetry, changeSearch }: { error: ApiError | null; onRetry: () => void; changeSearch: string }) {
  const code = error?.code;

  if (code === "unauthorized") {
    const next = typeof window === "undefined" ? "/ride" : `${window.location.pathname}${window.location.search}`;
    return (
      <Message title="Your session has ended">
        <p>Log in again to see trips.</p>
        <Link href={`/login?next=${encodeURIComponent(next)}`} className={buttonStyles({ size: "md", fullWidth: true })}>
          Log in
        </Link>
      </Message>
    );
  }

  if (code === "invalid_input") {
    return (
      <Message title="This search isn't valid">
        <p>Choose your area, direction and time again.</p>
        <Link href="/ride" className={buttonStyles({ size: "md", fullWidth: true })}>
          Start a new search
        </Link>
      </Message>
    );
  }

  const unavailable = code === "routing_unavailable" || code === "service_unavailable";
  return (
    <Message title={unavailable ? "Matching is unavailable right now" : "We couldn't load trips"}>
      <p>{unavailable ? "Trips can't be matched to your area at the moment. Try again in a minute." : error?.message}</p>
      <div className="flex gap-3">
        <Button size="md" fullWidth onClick={onRetry}>
          Try again
        </Button>
        <Link href={changeSearch} className={buttonStyles({ variant: "secondary", size: "md", fullWidth: true })}>
          Change search
        </Link>
      </div>
    </Message>
  );
}

function Message({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div role="alert" className="mt-8 space-y-4 text-ink-soft">
      <h1 className="text-2xl leading-tight text-ink">{title}</h1>
      {children}
    </div>
  );
}
