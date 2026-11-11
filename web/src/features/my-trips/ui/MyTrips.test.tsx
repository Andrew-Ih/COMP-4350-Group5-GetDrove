import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { RiderTrip, Trip } from "../model/myTrips";
import { MyTrips } from "./MyTrips";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/trips",
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

function inDays(days: number, time: string): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const [h, m] = time.split(":").map(Number);
  date.setHours(h!, m!, 0, 0);
  return date.toISOString();
}

const trip = (id: string, departureAt: string, changes: Partial<Trip> = {}): Trip => ({
  id,
  driverId: "1",
  direction: "to_campus",
  origin: { label: "Wolseley area", lat: 49.8794, lng: -97.1663 },
  destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
  departureAt,
  estimatedArrivalAt: new Date(Date.parse(departureAt) + 22 * 60_000).toISOString(),
  durationSeconds: 1320,
  distanceMeters: 11_800,
  seatsTotal: 3,
  seatsAvailable: 2,
  status: "scheduled",
  ...changes,
});

const ride = (id: string, status: RiderTrip["request"]["status"], tripChanges: Partial<Trip> = {}): RiderTrip => ({
  trip: trip(id, inDays(1, "07:52"), { origin: null, ...tripChanges }),
  request: {
    id: `req-${id}`,
    tripId: id,
    riderId: "1",
    status,
    pickup: { label: "Osborne St & River Ave", lat: 49.8768, lng: -97.1438, walkSeconds: 240 },
    cost: { amountCents: 420, currency: "CAD", explanation: "9.3 km at $0.45/km" },
    autoAccepted: false,
    createdAt: inDays(-1, "12:00"),
    decidedAt: null,
  },
});

type Answer = { status: number; body?: unknown };

/**
 * The API for these tests. Cancelling works like the real one: the trip (or every trip
 * in its series) comes back cancelled, and so do the lists after that. `cancelError`
 * makes cancelling fail instead.
 */
function api({
  rides = { upcoming: [ride("a", "pending"), ride("b", "accepted"), ride("c", "cancelled", { status: "cancelled" })], past: [] as RiderTrip[] },
  drives = { upcoming: [] as Trip[], past: [] as Trip[] },
  cancelError,
}: {
  rides?: { upcoming: RiderTrip[]; past: RiderTrip[] } | Answer;
  drives?: { upcoming: Trip[]; past: Trip[] };
  cancelError?: Answer;
} = {}) {
  const cancelled = new Set<string>();
  const current = (t: Trip): Trip => (cancelled.has(t.id) ? { ...t, status: "cancelled" } : t);
  const all = [...drives.upcoming, ...drives.past];
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    "/requests/mine": (url) =>
      "status" in rides ? rides : { status: 200, body: url.searchParams.get("when") === "past" ? rides.past : rides.upcoming },
    "/trips/mine": (url) => ({ status: 200, body: (url.searchParams.get("when") === "past" ? drives.past : drives.upcoming).map(current) }),
    "/cancel": (url) => {
      if (cancelError) return cancelError;
      const [kind, id] = url.pathname.split("/").slice(-3, -1);
      const trips = kind === "series" ? all.filter((t) => t.seriesId === id) : all.filter((t) => t.id === id);
      for (const t of trips) cancelled.add(t.id);
      const body = trips.map(current);
      return { status: 200, body: kind === "series" ? body : body[0] };
    },
  });
}

const section = (name: string) => screen.getByRole("region", { name });
const calls = (fetchSpy: ReturnType<typeof api>, path: string) =>
  fetchSpy.mock.calls.filter(([input]) => new URL(input instanceof Request ? input.url : String(input)).pathname.endsWith(path));

afterEach(() => vi.restoreAllMocks());

describe("MyTrips: riding", () => {
  it("lists upcoming rides with their status, pickup and price, each opening its trip", async () => {
    api();
    renderWithProviders(<MyTrips />);

    expect(screen.getByRole("tab", { name: "Riding" })).toHaveAttribute("aria-selected", "true");
    const rows = await within(section("Upcoming")).findAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Pending");
    expect(rows[0]).toHaveTextContent("Osborne St & River Ave");
    expect(rows[0]).toHaveTextContent("$4.20");
    expect(rows[1]).toHaveTextContent("Confirmed");
    expect(rows[2]).toHaveTextContent("Trip cancelled"); // still listed, marked cancelled
    expect(within(rows[0]!).getByRole("link")).toHaveAttribute("href", "/ride/trip/a");
  });

  it("asks for upcoming and past rides separately", async () => {
    const fetchSpy = api({ rides: { upcoming: [], past: [ride("p", "accepted", { status: "completed" })] } });
    renderWithProviders(<MyTrips />);

    expect(await within(section("Past")).findByText("Completed")).toBeInTheDocument();
    const whens = calls(fetchSpy, "/requests/mine").map(([input]) => new URL(input instanceof Request ? input.url : String(input)).searchParams.get("when"));
    expect(whens.sort()).toEqual(["past", "upcoming"]);
  });

  it("says when there are no rides yet, with a way to find one", async () => {
    api({ rides: { upcoming: [], past: [] } });
    renderWithProviders(<MyTrips />);

    expect(await within(section("Upcoming")).findByText("You haven't asked for a seat on any trips yet.")).toBeInTheDocument();
    expect(within(section("Upcoming")).getByRole("link", { name: "Find a ride" })).toHaveAttribute("href", "/ride");
    expect(await within(section("Past")).findByText("No past rides yet.")).toBeInTheDocument();
  });

  it("offers to try again when the rides can't be loaded", async () => {
    api({ rides: { status: 500, body: problem(500, "unexpected_error", "Something went wrong") } });
    renderWithProviders(<MyTrips />);

    expect(await within(section("Upcoming")).findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("asks the student to log in again when their session has ended", async () => {
    api({ rides: { status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") } });
    renderWithProviders(<MyTrips />);

    expect((await within(section("Upcoming")).findByRole("link", { name: "Log in" })).getAttribute("href")).toBe("/login?next=%2Ftrips");
  });
});

describe("MyTrips: driving", () => {
  const single = trip("t1", inDays(2, "08:00"));
  const seriesDay = trip("t2", inDays(3, "08:00"), { seriesId: "s1" });
  const nextInSeries = trip("t3", inDays(4, "08:00"), { seriesId: "s1" });
  const soon = trip("t4", new Date(Date.now() + 30 * 60_000).toISOString());
  const cancelled = trip("t5", inDays(5, "17:00"), { status: "cancelled" });
  const done = trip("t6", inDays(-2, "07:45"), { status: "completed", seatsAvailable: 0 });

  it("opens on the Driving tab when asked, and shows each trip's seats and status", async () => {
    api({ drives: { upcoming: [single, cancelled], past: [done] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    expect(screen.getByRole("tab", { name: "Driving" })).toHaveAttribute("aria-selected", "true");
    const [first, second] = await within(section("Upcoming")).findAllByRole("listitem");
    expect(first).toHaveTextContent("Wolseley area → U of M Fort Garry");
    expect(first).toHaveTextContent("1 of 3 seats filled");
    expect(within(first!).getByRole("link")).toHaveAttribute("href", "/drive/trips/t1");
    expect(second).toHaveTextContent("Cancelled");
    expect(within(second!).queryByRole("button", { name: "Cancel trip" })).not.toBeInTheDocument();
    expect(await within(section("Past")).findByText("Completed")).toBeInTheDocument();
    expect(within(section("Past")).queryByRole("button", { name: "Cancel trip" })).not.toBeInTheDocument();
  });

  it("switches between the tabs", async () => {
    api({ drives: { upcoming: [single], past: [] } });
    renderWithProviders(<MyTrips />);

    await userEvent.click(screen.getByRole("tab", { name: "Driving" }));
    expect(await within(section("Upcoming")).findByText("1 of 3 seats filled")).toBeInTheDocument();
  });

  it("says when no trips have been posted, with a way to post one", async () => {
    api();
    renderWithProviders(<MyTrips initialRole="driver" />);

    expect(await within(section("Upcoming")).findByText("You haven't posted any trips yet.")).toBeInTheDocument();
    expect(within(section("Upcoming")).getByRole("link", { name: "Post a trip" })).toHaveAttribute("href", "/drive/new");
  });

  it("cancels a trip after asking, and shows it as cancelled", async () => {
    const fetchSpy = api({ drives: { upcoming: [single], past: [] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel trip" }));
    const confirm = screen.getByRole("group", { name: "Cancel this trip?" });
    expect(confirm).toHaveTextContent("Riders on it will be told");
    expect(confirm).not.toHaveTextContent("late cancellation");

    await userEvent.click(within(confirm).getByRole("button", { name: "Cancel trip" }));

    expect(await within(section("Upcoming")).findByText("Cancelled")).toBeInTheDocument();
    expect(calls(fetchSpy, "/trips/t1/cancel")).toHaveLength(1);
  });

  it("keeps the trip when the driver changes their mind", async () => {
    const fetchSpy = api({ drives: { upcoming: [single], past: [] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel trip" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep trip" }));

    expect(screen.queryByRole("group", { name: "Cancel this trip?" })).not.toBeInTheDocument();
    expect(calls(fetchSpy, "/cancel")).toHaveLength(0);
  });

  it("cancels just one day of a recurring trip", async () => {
    const fetchSpy = api({ drives: { upcoming: [seriesDay, nextInSeries], past: [] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    const [first] = await within(section("Upcoming")).findAllByRole("listitem");
    await userEvent.click(within(first!).getByRole("button", { name: "Cancel trip" }));
    expect(within(first!).getByRole("radio", { name: /Just this day/ })).toBeChecked();
    await userEvent.click(within(first!).getByRole("button", { name: "Cancel trip" }));

    await waitFor(() => expect(calls(fetchSpy, "/trips/t2/cancel")).toHaveLength(1));
    expect(calls(fetchSpy, "/series/s1/cancel")).toHaveLength(0);
    // Only that day: the next trip in the series is still on.
    await waitFor(() => expect(within(section("Upcoming")).getAllByText("Cancelled")).toHaveLength(1));
  });

  it("cancels the whole series", async () => {
    const fetchSpy = api({ drives: { upcoming: [seriesDay, nextInSeries], past: [] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    const [first] = await within(section("Upcoming")).findAllByRole("listitem");
    await userEvent.click(within(first!).getByRole("button", { name: "Cancel trip" }));
    await userEvent.click(within(first!).getByRole("radio", { name: /The whole series/ }));
    await userEvent.click(within(first!).getByRole("button", { name: "Cancel series" }));

    await waitFor(() => expect(within(section("Upcoming")).getAllByText("Cancelled")).toHaveLength(2));
    expect(calls(fetchSpy, "/series/s1/cancel")).toHaveLength(1);
  });

  it("warns that cancelling within an hour of departure is a late cancellation", async () => {
    api({ drives: { upcoming: [soon], past: [] } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel trip" }));

    expect(screen.getByRole("group", { name: "Cancel this trip?" })).toHaveTextContent("counts as a late cancellation");
  });

  it("explains when the trip can't be cancelled anymore", async () => {
    api({ drives: { upcoming: [single], past: [] }, cancelError: { status: 409, body: problem(409, "trip_not_cancellable", "Already started") } });
    renderWithProviders(<MyTrips initialRole="driver" />);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel trip" }));
    await userEvent.click(within(screen.getByRole("group", { name: "Cancel this trip?" })).getByRole("button", { name: "Cancel trip" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This trip has already started or was cancelled");
  });
});
