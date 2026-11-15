import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MapMarker, MapRoute } from "@/shared/map";
import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { Trip } from "../model/postTrip";
import type { DriverRequest } from "../model/requests";
import { TripRequests } from "./TripRequests";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/drive/trips/t1",
}));

// The real map needs WebGL. This stand-in lists what it was asked to draw.
vi.mock("@/shared/map", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/shared/map")>();
  return {
    ...original,
    MapView: ({ routes = [], markers = [] }: { routes?: MapRoute[]; markers?: MapMarker[] }) => (
      <ul aria-label="map">
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

const TRIP_ID = "66666666-6666-4666-8666-666666666666";
const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

function tomorrowAt(time: string): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  const [h, m] = time.split(":").map(Number);
  date.setHours(h!, m!, 0, 0);
  return date.toISOString();
}

const trip = (changes: Partial<Trip> = {}): Trip => ({
  id: TRIP_ID,
  driverId: "1",
  direction: "to_campus",
  origin: { label: "Wolseley Ave & Arlington St", lat: 49.8794, lng: -97.1663 },
  destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
  departureAt: tomorrowAt("07:35"),
  estimatedArrivalAt: tomorrowAt("07:57"),
  durationSeconds: 1320,
  distanceMeters: 11_800,
  seatsTotal: 3,
  seatsAvailable: 1,
  status: "scheduled",
  ...changes,
});

function request(
  id: string,
  name: string,
  pickup: string,
  detourSeconds: number | null,
  status: "pending" | "accepted" = "pending",
  pickupOrder: number | null = null,
): DriverRequest {
  return {
    id,
    status,
    rider: { id: `r-${id}`, firstName: name, rating: name === "Sofia" ? null : 4.9, ratingCount: 8, noShowCount: name === "Ethan" ? 1 : 0 },
    pickup: { label: pickup, lat: 49.87, lng: -97.14 },
    pickupOrder,
    detourSeconds,
    cost: { amountCents: 420, currency: "CAD", explanation: "9.3 km at $0.45/km" },
    autoAccepted: false,
    createdAt: tomorrowAt("06:00"),
    decidedAt: null,
  };
}

const AMARA = request("q1", "Amara", "Osborne St & River Ave", 180);
const ETHAN = request("q2", "Ethan", "Corydon Ave & Stafford St", 300);
const LIAM = request("q4", "Liam", "Osborne St & Grant Ave", 120, "accepted", 1);
const NOOR = request("q5", "Noor", "Pembina Hwy & Bishop Grandin Blvd", 150, "accepted", 2);
const REQUESTS = [AMARA, ETHAN, LIAM, NOOR];

const ROUTE = {
  status: 200,
  body: {
    type: "Feature",
    geometry: { type: "LineString", coordinates: [[-97.1663, 49.8794], [-97.1366, 49.8075]] },
    properties: { tripId: TRIP_ID, distanceMeters: 11_800, durationSeconds: 1320 },
  },
};

type Answer = { status: number; body?: unknown };

/** Answers in order, repeating the last one: e.g. the list before and after a decision. */
function inTurn(...answers: Answer[]) {
  let i = 0;
  return () => answers[Math.min(i++, answers.length - 1)]!;
}

function api({
  detail = [{ status: 200, body: { trip: trip(), vehicle: null, pickups: [], myRequest: null } }],
  requests = [{ status: 200, body: REQUESTS }],
  accept = { status: 200, body: {} },
  decline = { status: 200, body: {} },
}: { detail?: Answer[]; requests?: Answer[]; accept?: Answer; decline?: Answer } = {}) {
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    [`/trips/${TRIP_ID}`]: inTurn(...detail),
    [`/trips/${TRIP_ID}/requests`]: inTurn(...requests),
    "/accept": accept,
    "/decline": decline,
    "/geometry": ROUTE,
  });
}

const callsTo = (fetchSpy: ReturnType<typeof api>, path: string) =>
  fetchSpy.mock.calls.filter(([input]) => new URL(input instanceof Request ? input.url : String(input)).pathname.endsWith(path));

const card = (name: string) => screen.getByRole("listitem", { name: `Request from ${name}` });

afterEach(() => vi.restoreAllMocks());

describe("TripRequests", () => {
  it("shows the trip, its seats and who's already riding", async () => {
    api();
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "Wolseley Ave & Arlington St → University Centre" })).toBeInTheDocument();
    expect(screen.getByText(/· Departs 7:35 AM$/)).toBeInTheDocument();
    expect(screen.getByText("2 of 3 seats filled")).toBeInTheDocument();
    expect(await screen.findByText("· Liam, Noor")).toBeInTheDocument();
    expect(screen.getByText("1 seat left")).toBeInTheDocument();

    const riders = within(screen.getByRole("list", { name: "Accepted riders" })).getAllByRole("listitem");
    expect(riders[0]).toHaveTextContent("Liam");
    expect(riders[0]).toHaveTextContent("1st pickup");
    expect(riders[1]).toHaveTextContent("Noor");
  });

  it("lists each pending request with the rider's rating, no-shows, pickup point and detour", async () => {
    api();
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "2 pending requests" })).toBeInTheDocument();
    expect(card("Amara")).toHaveTextContent("★ 4.9 · 0 no-shows");
    expect(card("Amara")).toHaveTextContent("Osborne St & River Ave");
    expect(within(card("Amara")).getByLabelText("Detour +3 min")).toBeInTheDocument();
    expect(card("Ethan")).toHaveTextContent("★ 4.9 · 1 no-show");
    expect(within(card("Ethan")).getByLabelText("Detour +5 min")).toBeInTheDocument();
  });

  it("puts the route, the accepted pickups and the requested ones on the map", async () => {
    api();
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    const map = screen.getByRole("list", { name: "map" });
    expect(await within(map).findByText("route trip")).toBeInTheDocument();
    expect(within(map).getByText("you Start · 7:35 AM")).toBeInTheDocument();
    expect(within(map).getByText("accepted Liam · accepted")).toBeInTheDocument();
    expect(within(map).getByText("stop Amara · +3 min")).toBeInTheDocument();
    expect(within(map).getByText("campus University Centre")).toBeInTheDocument();
  });

  it("accepts a request: the rider moves to the riders and the seats update straight away", async () => {
    const fetchSpy = api({
      requests: [
        { status: 200, body: REQUESTS },
        { status: 200, body: [ETHAN, LIAM, NOOR, { ...AMARA, status: "accepted", pickupOrder: 1 }] },
      ],
      detail: [
        { status: 200, body: { trip: trip(), vehicle: null, pickups: [], myRequest: null } },
        { status: 200, body: { trip: trip({ seatsAvailable: 0 }), vehicle: null, pickups: [], myRequest: null } },
      ],
    });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    await userEvent.click(await screen.findByRole("button", { name: "Accept Amara" }));

    expect(await screen.findByText("No seats left")).toBeInTheDocument();
    expect(screen.getByText("3 of 3 seats filled")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "1 pending request" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Accepted riders" })).getByText("Amara")).toBeInTheDocument();
    expect(callsTo(fetchSpy, "/requests/q1/accept")).toHaveLength(1);
    // The trip is full now, so the other request can only be declined.
    expect(screen.getByRole("button", { name: "Accept Ethan" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Decline Ethan" })).toBeEnabled();
  });

  it("declines a request: it leaves the list and the seats stay the same", async () => {
    const fetchSpy = api({ requests: [{ status: 200, body: REQUESTS }, { status: 200, body: [AMARA, LIAM, NOOR] }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    await userEvent.click(await screen.findByRole("button", { name: "Decline Ethan" }));

    expect(await screen.findByRole("heading", { name: "1 pending request" })).toBeInTheDocument();
    expect(screen.queryByRole("listitem", { name: "Request from Ethan" })).not.toBeInTheDocument();
    expect(screen.getByText("1 seat left")).toBeInTheDocument();
    expect(callsTo(fetchSpy, "/requests/q2/decline")).toHaveLength(1);
  });

  it("explains when the last seat was already taken, and refreshes the list", async () => {
    const fetchSpy = api({
      accept: { status: 409, body: problem(409, "seat_taken", "No seat left on this trip") },
      detail: [
        { status: 200, body: { trip: trip(), vehicle: null, pickups: [], myRequest: null } },
        { status: 200, body: { trip: trip({ seatsAvailable: 0 }), vehicle: null, pickups: [], myRequest: null } },
      ],
    });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    await userEvent.click(await screen.findByRole("button", { name: "Accept Amara" }));

    expect(await within(card("Amara")).findByRole("alert")).toHaveTextContent("Your trip is full now, so this request can't be accepted.");
    expect(await screen.findByText("No seats left")).toBeInTheDocument();
    await waitFor(() => expect(callsTo(fetchSpy, `/trips/${TRIP_ID}/requests`).length).toBeGreaterThan(1));
  });

  it("explains when the rider cancelled before the driver decided", async () => {
    api({ decline: { status: 409, body: problem(409, "request_not_decidable", "This request can't be declined") } });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    await userEvent.click(await screen.findByRole("button", { name: "Decline Amara" }));

    expect(await within(card("Amara")).findByRole("alert")).toHaveTextContent("This request has changed");
  });

  it("shows an error, not a number, when the detour couldn't be worked out, and tries again", async () => {
    const SOFIA = request("q3", "Sofia", "Pembina Hwy & Jubilee Ave", null);
    const fetchSpy = api({ requests: [{ status: 200, body: [SOFIA] }, { status: 200, body: [{ ...SOFIA, detourSeconds: 240 }] }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await within(await screen.findByRole("listitem", { name: "Request from Sofia" })).findByText(/Couldn't work out the detour/)).toBeInTheDocument();
    expect(card("Sofia")).toHaveTextContent("New rider · 0 no-shows");
    expect(within(card("Sofia")).queryByLabelText(/^Detour/)).not.toBeInTheDocument();

    await userEvent.click(within(card("Sofia")).getByRole("button", { name: "Try again" }));

    expect(await within(card("Sofia")).findByLabelText("Detour +4 min")).toBeInTheDocument();
    expect(callsTo(fetchSpy, `/trips/${TRIP_ID}/requests`)).toHaveLength(2);
  });

  it("shows Calculating… while the detour is being worked out again", async () => {
    const SOFIA = request("q3", "Sofia", "Pembina Hwy & Jubilee Ave", null);
    let release: () => void = () => {};
    const slow = new Promise<void>((resolve) => (release = resolve));
    let calls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : String(input)).pathname;
      const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
      if (path.endsWith("/accounts/me")) return json(200, maya);
      if (path.endsWith("/requests")) {
        calls += 1;
        if (calls > 1) await slow;
        return json(200, [calls > 1 ? { ...SOFIA, detourSeconds: 240 } : SOFIA]);
      }
      if (path.endsWith("/geometry")) return json(200, ROUTE.body);
      return json(200, { trip: trip(), vehicle: null, pickups: [], myRequest: null });
    });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

    expect(within(card("Sofia")).getByRole("status")).toHaveTextContent("Calculating…");
    release();
    expect(await within(card("Sofia")).findByLabelText("Detour +4 min")).toBeInTheDocument();
  });

  it("says when there are no pending requests yet", async () => {
    api({
      detail: [{ status: 200, body: { trip: trip({ seatsAvailable: 3 }), vehicle: null, pickups: [], myRequest: null } }],
      requests: [{ status: 200, body: [] }],
    });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "No pending requests" })).toBeInTheDocument();
    expect(screen.getByText("3 seats left")).toBeInTheDocument();
    expect(screen.getByText("0 of 3 seats filled")).toBeInTheDocument();
  });

  it("shows the requests without Accept or Decline once the trip has left", async () => {
    api({ detail: [{ status: 200, body: { trip: trip({ status: "in_progress" }), vehicle: null, pickups: [], myRequest: null } }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByText("This trip has already left, so requests can't be changed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Accept/ })).not.toBeInTheDocument();
  });

  it("says when the trip was cancelled", async () => {
    api({ detail: [{ status: 200, body: { trip: trip({ status: "cancelled" }), vehicle: null, pickups: [], myRequest: null } }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByText("This trip was cancelled.")).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    api();
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(screen.getByText("Loading your trip…")).toBeInTheDocument();
  });

  it("tells a student who isn't the driver that this isn't their trip", async () => {
    api({
      detail: [{ status: 200, body: { trip: trip({ driverId: "someone-else" }), vehicle: null, pickups: [], myRequest: null } }],
      requests: [{ status: 403, body: problem(403, "not_trip_driver", "Only the trip's driver can see its requests") }],
    });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "This isn't your trip" })).toBeInTheDocument();
  });

  it("says when the trip doesn't exist", async () => {
    api({ detail: [{ status: 404, body: problem(404, "trip_not_found", "No trip with this ID") }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "This trip no longer exists" })).toBeInTheDocument();
  });

  it("offers to try again when the requests can't be loaded", async () => {
    const failed = { status: 500, body: problem(500, "unexpected_error", "Something went wrong") };
    const fetchSpy = api({ requests: [failed, failed, { status: 200, body: REQUESTS }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    // A server error is retried once on its own before the error shows.
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }, { timeout: 4000 }));
    expect(await screen.findByRole("heading", { name: "2 pending requests" })).toBeInTheDocument();
    expect(callsTo(fetchSpy, `/trips/${TRIP_ID}/requests`)).toHaveLength(3);
  });

  it("asks the driver to log in again when their session has ended", async () => {
    api({ detail: [{ status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") }] });
    renderWithProviders(<TripRequests tripId={TRIP_ID} />);

    expect(await screen.findByRole("heading", { name: "Your session has ended" })).toBeInTheDocument();
  });
});
