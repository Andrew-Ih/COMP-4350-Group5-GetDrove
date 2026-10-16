import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MapMarker, MapRoute } from "@/shared/map";
import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { SearchResult } from "../model/results";
import { defaultWhen, type SearchQuery, toSearchTime } from "../model/search";
import { TripResults } from "./TripResults";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/ride/results",
}));

// The real map needs WebGL. This stand-in lists what it was asked to draw, and what it
// keeps in view (it only re-fits when that key changes).
vi.mock("@/shared/map", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/shared/map")>();
  return {
    ...original,
    MapView: ({ routes = [], markers = [], fitTo }: { routes?: MapRoute[]; markers?: MapMarker[]; fitTo?: { key: string } }) => (
      <ul aria-label="map">
        <li>fit {fitTo?.key}</li>
        {routes.map((r) => (
          <li key={r.id}>route {r.id}</li>
        ))}
        {markers.map((m) => (
          <li key={m.id}>
            {m.kind} {m.label}
          </li>
        ))}
      </ul>
    ),
  };
});

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

// Tomorrow, arriving by 8:30 AM, from Osborne Village.
const tomorrow = defaultWhen("to_campus");
const query: SearchQuery = {
  lat: 49.8768,
  lng: -97.1438,
  direction: "to_campus",
  time: toSearchTime(tomorrow.date, "08:30")!,
};
const at = (time: string) => toSearchTime(tomorrow.date, time)!;

function result(id: string, departs: string, pickup: string, cents: number | null, walkSeconds = 240): SearchResult {
  return {
    trip: {
      id,
      driverId: `driver-${id}`,
      direction: "to_campus",
      origin: null,
      destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
      departureAt: at(departs),
      estimatedArrivalAt: at("08:15"),
      durationSeconds: 1440,
      distanceMeters: 14_000,
      seatsTotal: 3,
      seatsAvailable: id === "a" ? 1 : 2,
      status: "scheduled",
    },
    pickup: { label: pickup, lat: 49.87, lng: -97.14, walkSeconds },
    cost: cents === null ? null : { amountCents: cents, currency: "CAD", explanation: "9.3 km at $0.45/km" },
  };
}

const RESULTS = [
  result("a", "07:44", "Corydon Ave & Osborne St", 460, 360),
  result("b", "07:48", "Osborne St & River Ave", 420, 180),
];

const route = (tripId: string) => ({
  status: 200,
  body: {
    type: "Feature",
    geometry: { type: "LineString", coordinates: [[-97.17, 49.88], [-97.1366, 49.8075]] },
    properties: { tripId, distanceMeters: 14_000, durationSeconds: 1440 },
  },
});

function api(search: { status: number; body?: unknown } = { status: 200, body: RESULTS }) {
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    "/trips/search": search,
    "/geometry": (url) => route(url.pathname.split("/").at(-2)!),
  });
}

const cards = () => within(screen.getByRole("radiogroup", { name: "Trips" })).getAllByRole("radio");

afterEach(() => vi.restoreAllMocks());

describe("TripResults", () => {
  it("searches with the contract's fields and lists each trip with the rider's share", async () => {
    const fetchSpy = api();
    renderWithProviders(<TripResults query={query} />);

    expect(screen.getByText("Osborne Village → U of M Fort Garry")).toBeInTheDocument();
    expect(screen.getByText("Tomorrow · arrive by 8:30 AM")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "2 trips tomorrow" })).toBeInTheDocument();

    const searchUrl = fetchSpy.mock.calls
      .map(([input]) => new URL(input instanceof Request ? input.url : String(input)))
      .find((url) => url.pathname.endsWith("/trips/search"))!;
    expect(Object.fromEntries(searchUrl.searchParams)).toEqual({
      lat: "49.8768",
      lng: "-97.1438",
      direction: "to_campus",
      time: query.time,
    });

    const [first] = cards();
    expect(first).toHaveTextContent("Departs 7:44 AM");
    expect(first).toHaveTextContent("Arrives 8:15 AM · 1 seat left");
    expect(first).toHaveTextContent("6 min walk to Corydon Ave & Osborne St");
    expect(first).toHaveTextContent("$4.60");
    expect(first).toHaveTextContent("your share");
  });

  it("selects the first trip and shows its route, pickup and how the share was worked out", async () => {
    api();
    renderWithProviders(<TripResults query={query} />);

    await screen.findByRole("heading", { name: "2 trips tomorrow" });
    expect(cards()[0]).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(/your share: 9.3 km at \$0.45\/km/)).toBeInTheDocument();
    const map = screen.getByRole("list", { name: "map" });
    expect(within(map).getByText("pickup Corydon Ave & Osborne St")).toBeInTheDocument();
    expect(within(map).getByText("stop 7:48 AM")).toBeInTheDocument(); // the other trip
    expect(await within(map).findByText("route selected")).toBeInTheDocument();
    expect(await within(map).findByText("route other-b")).toBeInTheDocument(); // the other trip, in grey
    expect(within(map).getByText("route walk")).toBeInTheDocument();
  });

  it("highlights another trip when it's chosen, without moving the map", async () => {
    api();
    renderWithProviders(<TripResults query={query} />);

    await screen.findByRole("heading", { name: "2 trips tomorrow" });
    const map = screen.getByRole("list", { name: "map" });
    await within(map).findByText("route other-b");
    expect(within(map).getByText("fit a,b")).toBeInTheDocument();

    await userEvent.click(cards()[1]!);

    expect(cards()[1]).toHaveAttribute("aria-checked", "true");
    expect(cards()[0]).toHaveAttribute("aria-checked", "false");
    expect(within(map).getByText("pickup Osborne St & River Ave")).toBeInTheDocument();
    expect(within(map).getByText("route other-a")).toBeInTheDocument(); // the first trip is grey now
    expect(within(map).getByText("fit a,b")).toBeInTheDocument(); // same view: the map doesn't move
  });

  it("doesn't move the map when the list is sorted", async () => {
    api();
    renderWithProviders(<TripResults query={query} />);

    await screen.findByRole("heading", { name: "2 trips tomorrow" });
    await userEvent.selectOptions(screen.getByLabelText("Sort by"), "Cheapest");

    expect(within(screen.getByRole("list", { name: "map" })).getByText("fit a,b")).toBeInTheDocument();
  });

  it("sorts by price", async () => {
    api();
    renderWithProviders(<TripResults query={query} />);

    await screen.findByRole("heading", { name: "2 trips tomorrow" });
    await userEvent.selectOptions(screen.getByLabelText("Sort by"), "Cheapest");

    expect(cards()[0]).toHaveTextContent("$4.20");
    expect(cards()[1]).toHaveTextContent("$4.60");
  });

  it("still lists a trip whose price can't be worked out", async () => {
    api({ status: 200, body: [result("a", "07:44", "Corydon Ave & Osborne St", null)] });
    renderWithProviders(<TripResults query={query} />);

    expect(await screen.findByRole("heading", { name: "1 trip tomorrow" })).toBeInTheDocument();
    expect(cards()[0]).toHaveTextContent("Price unavailable");
    expect(screen.queryByLabelText("Sort by")).not.toBeInTheDocument();
  });

  it("says when no trips pass nearby, with a way back to the same search", async () => {
    api({ status: 200, body: [] });
    renderWithProviders(<TripResults query={query} />);

    expect(await screen.findByRole("heading", { name: "No trips tomorrow" })).toBeInTheDocument();
    const change = screen.getAllByRole("link", { name: "Change search" });
    for (const link of change) {
      expect(link.getAttribute("href")).toMatch(/^\/ride\?lat=49\.87680&lng=-97\.14380&direction=to_campus&time=/);
    }
  });

  it("offers to try again when matching is unavailable", async () => {
    const fetchSpy = api({ status: 503, body: problem(503, "routing_unavailable", "Matching is unavailable right now") });
    renderWithProviders(<TripResults query={query} />);

    expect(await screen.findByRole("heading", { name: "Matching is unavailable right now" })).toBeInTheDocument();
    const searches = () =>
      fetchSpy.mock.calls.filter(([input]) => String(input instanceof Request ? input.url : input).includes("/trips/search")).length;
    expect(searches()).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(searches()).toBe(2));
  });

  it("asks the student to log in again when their session has ended", async () => {
    api({ status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") });
    renderWithProviders(<TripResults query={query} />);

    expect(await screen.findByRole("heading", { name: "Your session has ended" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href")).toMatch(/^\/login\?next=/);
  });

  it("keeps the list when a trip's route can't be loaded", async () => {
    mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/trips/search": { status: 200, body: RESULTS },
      "/geometry": { status: 404, body: problem(404, "route_not_found", "No route for this trip") },
    });
    renderWithProviders(<TripResults query={query} />);

    expect(await screen.findByRole("heading", { name: "2 trips tomorrow" })).toBeInTheDocument();
    expect(screen.queryByText("route selected")).not.toBeInTheDocument();
    expect(cards()).toHaveLength(2);
  });

  it("doesn't search when the link is missing a field", () => {
    const fetchSpy = api();
    renderWithProviders(<TripResults query={undefined} />);

    expect(screen.getByRole("heading", { name: "This search link is incomplete" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new search" })).toHaveAttribute("href", "/ride");
    expect(fetchSpy.mock.calls.some(([input]) => String(input instanceof Request ? input.url : input).includes("/trips/search"))).toBe(
      false,
    );
  });
});
