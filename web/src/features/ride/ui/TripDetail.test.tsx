import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MapMarker, MapRoute } from "@/shared/map";
import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import { defaultWhen, type SearchQuery, toSearchTime } from "../model/search";
import type { DriverProfile, PickupOption, TripDetail as Detail } from "../model/tripDetail";
import { TripDetail } from "./TripDetail";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/ride/trip/t1",
}));

// The real map needs WebGL. This stand-in lists what it was asked to draw.
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

const TRIP_ID = "22222222-2222-4222-8222-222222222222";
const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

// Tomorrow, arriving by 8:30 AM, from Osborne Village.
const tomorrow = defaultWhen("to_campus");
const at = (time: string) => toSearchTime(tomorrow.date, time)!;
const search: SearchQuery = { lat: 49.8768, lng: -97.1438, direction: "to_campus", time: at("08:30") };

const pickup = (id: string, label: string, walkSeconds: number, cents: number | null): PickupOption => ({
  id,
  label,
  lat: 49.877,
  lng: -97.141,
  walkSeconds,
  cost: cents === null ? null : { amountCents: cents, currency: "CAD", explanation: "Based on 9.2 km of a 14 km trip" },
});

const PICKUPS = [
  pickup("s1", "Osborne St & River Ave", 240, 420),
  pickup("s2", "Osborne St & Wardlaw Ave", 420, 400),
  pickup("s3", "River Ave & Nassau St", 360, 430),
];

function detail(changes: Partial<Detail> = {}, trip: Partial<Detail["trip"]> = {}): Detail {
  return {
    trip: {
      id: TRIP_ID,
      driverId: "d1",
      direction: "to_campus",
      origin: null,
      destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
      departureAt: at("07:48"),
      estimatedArrivalAt: at("08:12"),
      durationSeconds: 1440,
      distanceMeters: 14_000,
      seatsTotal: 3,
      seatsAvailable: 2,
      status: "scheduled",
      ...trip,
    },
    vehicle: null,
    pickups: PICKUPS,
    myRequest: null,
    ...changes,
  };
}

const priya: DriverProfile = {
  id: "d1",
  firstName: "Priya",
  rating: 4.9,
  ratingCount: 52,
  tripCount: 61,
  isDriver: true,
  vehicle: { make: "Honda", model: "Civic", colour: "Grey" },
};

const ROUTE = {
  status: 200,
  body: {
    type: "Feature",
    geometry: { type: "LineString", coordinates: [[-97.17, 49.88], [-97.1366, 49.8075]] },
    properties: { tripId: TRIP_ID, distanceMeters: 14_000, durationSeconds: 1440 },
  },
};

type Answer = { status: number; body?: unknown };

function api(trip: Answer = { status: 200, body: detail() }, profile: Answer = { status: 200, body: priya }) {
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    [`/trips/${TRIP_ID}`]: trip,
    "/profile": profile,
    "/geometry": ROUTE,
  });
}

const urlsOf = (fetchSpy: ReturnType<typeof api>) =>
  fetchSpy.mock.calls.map(([input]) => new URL(input instanceof Request ? input.url : String(input)));

afterEach(() => vi.restoreAllMocks());

describe("TripDetail", () => {
  it("asks for pickup points near the rider and shows the driver, stops and share", async () => {
    const fetchSpy = api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "Priya" })).toBeInTheDocument();
    const tripUrl = urlsOf(fetchSpy).find((url) => url.pathname.endsWith(`/trips/${TRIP_ID}`))!;
    expect(Object.fromEntries(tripUrl.searchParams)).toEqual({ lat: "49.8768", lng: "-97.1438" });

    expect(await screen.findByText("★ 4.9 · Grey Honda Civic")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 seats left · departs 7:48 AM tomorrow")).toBeInTheDocument();

    const [first, second] = within(screen.getByRole("list", { name: "Stops" })).getAllByRole("listitem");
    expect(first).toHaveTextContent("Pickup");
    expect(first).toHaveTextContent("Osborne St & River Ave");
    expect(first).toHaveTextContent("4 min walk from your area");
    expect(second).toHaveTextContent("Drop-off · 8:12 AM");
    expect(second).toHaveTextContent("University Centre");

    expect(screen.getByText("Based on 9.2 km of a 14 km trip")).toBeInTheDocument();
    expect(screen.getByText("$4.20")).toBeInTheDocument();
    expect(screen.getByText(/Priya will see this pickup point, never your address/)).toBeInTheDocument();
  });

  it("draws the route, the pickup point, the other points and the walk on the map", async () => {
    api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    const map = screen.getByRole("list", { name: "map" });
    expect(await within(map).findByText("route trip")).toBeInTheDocument();
    expect(within(map).getByText("pickup Osborne St & River Ave")).toBeInTheDocument();
    expect(within(map).getAllByText(/^stop\s*$/)).toHaveLength(2); // the other points, without labels
    expect(within(map).getByText("route walk")).toBeInTheDocument();
    expect(within(map).getByText("you You")).toBeInTheDocument();
  });

  it("goes back to the same results", async () => {
    api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(screen.getByRole("link", { name: "All trips" }).getAttribute("href")).toMatch(
      /^\/ride\/results\?lat=49\.87680&lng=-97\.14380&direction=to_campus&time=/,
    );
  });

  it("lets the rider choose a different pickup point, with its walk and price", async () => {
    api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    await userEvent.click(await screen.findByRole("button", { name: "Choose a different pickup point" }));
    const choices = within(screen.getByRole("radiogroup", { name: "Points near you" })).getAllByRole("radio");
    expect(choices).toHaveLength(3);
    expect(choices[0]).toHaveAttribute("aria-checked", "true");
    expect(choices[1]).toHaveTextContent("Osborne St & Wardlaw Ave");
    expect(choices[1]).toHaveTextContent("7 min walk");
    expect(choices[1]).toHaveTextContent("$4.00");

    await userEvent.click(choices[1]!);

    expect(screen.queryByRole("radiogroup", { name: "Points near you" })).not.toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Stops" })).getAllByRole("listitem")[0]).toHaveTextContent(
      "Osborne St & Wardlaw Ave",
    );
    expect(screen.getByRole("button", { name: /Request seat · \$4\.00/ })).toBeInTheDocument();
    const map = screen.getByRole("list", { name: "map" });
    expect(within(map).getByText("pickup Osborne St & Wardlaw Ave")).toBeInTheDocument();
    expect(within(map).getAllByText(/^stop\s*$/)).toHaveLength(2);
  });

  it("doesn't offer other points when there's only one", async () => {
    api({ status: 200, body: detail({ pickups: [PICKUPS[0]!] }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    await screen.findByRole("heading", { name: "Priya" });
    expect(screen.queryByRole("button", { name: "Choose a different pickup point" })).not.toBeInTheDocument();
  });

  it("shows the request button, not yet active (the request flow is #141)", async () => {
    api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("button", { name: /Request seat · \$4\.20/ })).toBeDisabled();
  });

  it("says when a pickup point can't be priced", async () => {
    api({ status: 200, body: detail({ pickups: [pickup("s1", "Osborne St & River Ave", 240, null)] }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByText("The price can't be worked out right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request seat" })).toBeDisabled();
  });

  it("puts the campus first and the point near the rider last on a trip home", async () => {
    api({
      status: 200,
      body: detail({}, { direction: "from_campus", origin: { label: "University Centre", lat: 49.8075, lng: -97.1366 }, destination: null }),
    });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={{ ...search, direction: "from_campus" }} />);

    await screen.findByRole("heading", { name: "Priya" });
    const [first, second] = within(screen.getByRole("list", { name: "Stops" })).getAllByRole("listitem");
    expect(first).toHaveTextContent("Pickup · 7:48 AM");
    expect(first).toHaveTextContent("University Centre");
    expect(second).toHaveTextContent("Drop-off");
    expect(second).toHaveTextContent("4 min walk to your area");
    expect(screen.getByRole("button", { name: "Choose a different drop-off point" })).toBeInTheDocument();
  });

  it("shows the rider's pending request instead of the button", async () => {
    const request = {
      id: "r1",
      tripId: TRIP_ID,
      riderId: "1",
      status: "pending" as const,
      pickup: { label: "Osborne St & Wardlaw Ave", lat: 49.877, lng: -97.141, walkSeconds: 420 },
      cost: { amountCents: 400, currency: "CAD" as const, explanation: "Based on 9.0 km of a 14 km trip" },
      autoAccepted: false,
      createdAt: at("06:00"),
      decidedAt: null,
    };
    api({ status: 200, body: detail({ myRequest: request }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByText("Request sent")).toBeInTheDocument();
    // The driver's name arrives with their profile, a moment after the trip.
    expect(await screen.findByText(/Waiting for Priya to accept/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Request seat/ })).not.toBeInTheDocument();
    // The request's own pickup and price, and no switching once it's sent.
    expect(within(screen.getByRole("list", { name: "Stops" })).getAllByRole("listitem")[0]).toHaveTextContent(
      "Osborne St & Wardlaw Ave",
    );
    expect(screen.getByText("$4.00")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Choose a different pickup point" })).not.toBeInTheDocument();
  });

  it("shows the car and plate once the rider is accepted", async () => {
    const accepted = {
      id: "r1",
      tripId: TRIP_ID,
      riderId: "1",
      status: "accepted" as const,
      pickup: { label: "Osborne St & River Ave", lat: 49.877, lng: -97.141, walkSeconds: 240 },
      cost: { amountCents: 420, currency: "CAD" as const, explanation: "Based on 9.2 km of a 14 km trip" },
      autoAccepted: true,
      createdAt: at("06:00"),
      decidedAt: at("06:01"),
    };
    const vehicle = { make: "Honda", model: "Civic", colour: "Grey", plate: "ABC123" };
    api({ status: 200, body: detail({ myRequest: accepted, vehicle }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByText("You're in")).toBeInTheDocument();
    expect(screen.getByText(/Look for a Grey Honda Civic, plate ABC123/)).toBeInTheDocument();
    expect(await screen.findByText("★ 4.9 · Grey Honda Civic · ABC123")).toBeInTheDocument();
  });

  it("says when the trip is full", async () => {
    api({ status: 200, body: detail({}, { seatsAvailable: 0 }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByText("No seats left")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Request seat/ })).not.toBeInTheDocument();
  });

  it("says when the driver cancelled the trip", async () => {
    api({ status: 200, body: detail({}, { status: "cancelled" }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "This trip was cancelled" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "All trips" })).toHaveLength(2);
  });

  it("says when the trip has already left", async () => {
    api({ status: 200, body: detail({}, { status: "in_progress" }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "This trip has already left" })).toBeInTheDocument();
  });

  it("says when the trip no longer passes near the rider", async () => {
    api({ status: 200, body: detail({ pickups: [] }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByText("This trip no longer passes within walking distance of your area.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Request seat/ })).not.toBeInTheDocument();
  });

  it("opened without a search, shows the trip and asks the rider to search for pickup points", async () => {
    const fetchSpy = api({ status: 200, body: detail({ pickups: [] }) });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={undefined} />);

    expect(await screen.findByText("Search from your area to see where you'd be picked up.")).toBeInTheDocument();
    const tripUrl = urlsOf(fetchSpy).find((url) => url.pathname.endsWith(`/trips/${TRIP_ID}`))!;
    expect(tripUrl.search).toBe("");
    expect(screen.getByRole("link", { name: "Find a ride" })).toHaveAttribute("href", "/ride");
  });

  it("shows a loading state first", () => {
    api();
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(screen.getByText("Loading trip…")).toBeInTheDocument();
  });

  it("says when the trip no longer exists, and doesn't ask for its route", async () => {
    const fetchSpy = api({ status: 404, body: problem(404, "trip_not_found", "No trip with this ID") });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "This trip is no longer available" })).toBeInTheDocument();
    expect(urlsOf(fetchSpy).some((url) => url.pathname.endsWith("/geometry"))).toBe(false);
  });

  it("offers to try again when pickup points can't be worked out", async () => {
    const fetchSpy = api({ status: 503, body: problem(503, "routing_unavailable", "Pickup points can't be worked out right now") });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "Pickup points are unavailable right now" })).toBeInTheDocument();
    const tripCalls = () => urlsOf(fetchSpy).filter((url) => url.pathname.endsWith(`/trips/${TRIP_ID}`)).length;
    expect(tripCalls()).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(tripCalls()).toBe(2));
  });

  it("asks the student to log in again when their session has ended", async () => {
    api({ status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "Your session has ended" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href")).toMatch(/^\/login\?next=/);
  });

  it("still shows the trip when the driver's profile can't be loaded", async () => {
    api(undefined, { status: 404, body: problem(404, "user_not_found", "No user with this ID") });
    renderWithProviders(<TripDetail tripId={TRIP_ID} search={search} />);

    expect(await screen.findByRole("heading", { name: "Your driver" })).toBeInTheDocument();
    expect(screen.getByText("$4.20")).toBeInTheDocument();
    expect(screen.getByText(/The driver will see this pickup point/)).toBeInTheDocument();
  });
});
