"use client";

import { MapPin, Search } from "lucide-react";
import { type FormEvent, useId, useState } from "react";

import type { LngLat } from "@/shared/map";
import { Button } from "@/shared/ui";

import { useFindPlaces } from "../hooks/useFindPlaces";
import { MIN_QUERY_LENGTH, NOT_FOUND_MESSAGE, placeErrorMessage, placePoint, TOO_SHORT_MESSAGE } from "../model/places";

/**
 * Choose your area by typing an address or a place (#257), as an alternative to tapping the
 * map or sharing your location. The user types, presses Search and picks one of the matches;
 * picking one calls `onPick` with its point, exactly like tapping the map there.
 *
 * What was typed is sent once per search, never in the URL or browser storage. It's held in
 * memory only while the matches are on screen: picking one, or typing again, drops it.
 */
export function AddressSearch({ onPick, className }: { onPick: (point: LngLat) => void; className?: string }) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<string>();
  const [showMatches, setShowMatches] = useState(false);
  const search = useFindPlaces();

  function submit(event: FormEvent) {
    event.preventDefault();
    const typed = query.trim();
    if (typed.length < MIN_QUERY_LENGTH) {
      setMessage(TOO_SHORT_MESSAGE);
      return;
    }
    setMessage(undefined);
    search.mutate(typed, {
      onSuccess: ({ places }) => {
        setShowMatches(places.length > 0);
        if (places.length === 0) setMessage(NOT_FOUND_MESSAGE);
      },
      onError: (error) => {
        setShowMatches(false);
        setMessage(placeErrorMessage(error));
      },
    });
  }

  const places = showMatches ? (search.data?.places ?? []) : [];

  return (
    <div className={className}>
      <form role="search" aria-label="Find an address" onSubmit={submit} className="flex items-center gap-2">
        <label htmlFor={`${id}-address`} className="sr-only">
          Address or place
        </label>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-surface-muted px-3">
          <Search aria-hidden="true" className="size-4 shrink-0 text-ink-soft" />
          <input
            id={`${id}-address`}
            type="search"
            enterKeyHint="search"
            autoComplete="off"
            maxLength={200}
            placeholder="Or type an address"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setMessage(undefined);
              // Old matches, or a search still running, are for what was typed before: drop
              // them, so a late answer never shows matches for text that has since changed.
              setShowMatches(false);
              search.reset();
            }}
            className="h-10 min-w-0 flex-1 bg-transparent font-semibold outline-none placeholder:text-subtle"
          />
        </div>
        <Button type="submit" size="sm" variant="dark" loading={search.isPending}>
          Search
        </Button>
      </form>

      {places.length > 0 && (
        <ul aria-label="Matching places" className="mt-2 divide-y divide-line rounded-md border border-line bg-surface">
          {places.map((place) => (
            <li key={`${place.label}-${place.lat}-${place.lng}`}>
              <button
                type="button"
                onClick={() => {
                  onPick(placePoint(place));
                  setShowMatches(false);
                  setQuery("");
                  search.reset(); // drops what was typed and the matches
                }}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left font-semibold hover:bg-surface-muted"
              >
                <MapPin aria-hidden="true" className="size-4 shrink-0 text-ink-soft" />
                <span className="min-w-0 truncate">{place.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <p role="status" className="mt-1 min-h-5 text-sm font-semibold text-danger">
        {message ?? ""}
      </p>
      {places.length > 0 && (
        <p className="text-xs text-subtle">
          Addresses from{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline">
            OpenStreetMap
          </a>
        </p>
      )}
    </div>
  );
}
