import { http, HttpResponse } from "msw";

import type { components as Routing } from "@/shared/api/generated/routing";

/**
 * Mock API for typing an address (#257), matching the Routing contract. A few real
 * Winnipeg places; anything else finds nothing. "slow lookup" answers 503, to see the
 * message for when the address lookup is down.
 */

type Place = Routing["schemas"]["Place"];

export const MOCK_PLACES: Place[] = [
  { label: "750 Osborne Street, Fort Rouge", lat: 49.8664, lng: -97.1386 },
  { label: "CF Polo Park, St. James", lat: 49.881, lng: -97.2005 },
  { label: "The Forks, Downtown", lat: 49.8875, lng: -97.1306 },
  { label: "St. Vital Centre, St. Vital", lat: 49.8236, lng: -97.1006 },
];

export const placeHandlers = [
  http.post("*/api/routing/places", async ({ request }) => {
    const { query } = (await request.json()) as Routing["schemas"]["PlaceSearchRequest"];
    const typed = query.trim().toLowerCase();
    if (typed === "slow lookup") {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "Address lookup unavailable",
          status: 503,
          detail: "We can't look up addresses right now.",
          instance: "/api/routing/places",
          code: "geocoding_unavailable",
          requestId: "mock",
        },
        { status: 503, headers: { "Content-Type": "application/problem+json" } },
      );
    }
    const words = typed.split(/\s+/);
    const places = MOCK_PLACES.filter((place) => words.every((word) => place.label.toLowerCase().includes(word)));
    return HttpResponse.json({ places } satisfies Routing["schemas"]["PlaceSearchResponse"]);
  }),
];
