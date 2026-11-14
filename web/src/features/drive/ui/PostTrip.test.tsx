import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toSearchTime } from "@/features/ride";
import type { LngLat, MapMarker, MapRoute } from "@/shared/map";
import { mockFetch, problem, renderWithProviders } from "@/shared/testing/render";

import { addDays, defaultDeparture, formatDate } from "../model/postTrip";
import { PostTrip } from "./PostTrip";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/drive/new",
}));

// The real map needs WebGL. This stand-in "taps" a point and lists what it draws.
let tapPoint: LngLat = [-97.1438, 49.8768]; // Osborne Village
vi.mock("@/shared/map", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/shared/map")>();
  return {
    ...original,
    MapView: ({ onPick, routes = [], markers = [] }: { onPick?: (p: LngLat) => void; routes?: MapRoute[]; markers?: MapMarker[] }) => (
      <div>
        {onPick && (
          <button type="button" onClick={() => onPick(tapPoint)}>
            tap the map
          </button>
        )}
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
      </div>
    ),
  };
});

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };
const tomorrow = defaultDeparture("to_campus").date;

function postedTrip(direction: "to_campus" | "from_campus", departureAt: string, seats: number) {
  const departs = Date.parse(departureAt);
  return {
    id: "trip-1",
    driverId: "1",
    direction,
    origin: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
    destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
    departureAt,
    estimatedArrivalAt: new Date(departs + 22 * 60_000).toISOString(),
    durationSeconds: 1320,
    distanceMeters: 14_200,
    seatsTotal: seats,
    seatsAvailable: seats,
    status: "scheduled",
  };
}

const route = {
  type: "Feature",
  geometry: { type: "LineString", coordinates: [[-97.1438, 49.8768], [-97.1366, 49.8075]] },
  properties: { tripId: "trip-1", distanceMeters: 14_200, durationSeconds: 1320 },
};

/** No trips posted yet: GET /api/trips/mine?role=driver, checked just before posting. */
const NO_TRIPS = { status: 200, body: [] };

/** The body of the POST /api/trips/ request, if one was sent. */
async function postedBody(fetchSpy: ReturnType<typeof mockFetch>) {
  const request = fetchSpy.mock.calls.map(([input]) => input as Request).find((r) => r.method === "POST");
  return request ? await request.clone().json() : undefined;
}

beforeEach(() => {
  tapPoint = [-97.1438, 49.8768];
});
afterEach(() => vi.restoreAllMocks());

describe("PostTrip", () => {
  it("starts with sensible choices and waits for an area", () => {
    mockFetch({ status: 200, body: maya });
    renderWithProviders(<PostTrip />);

    expect(screen.getByRole("radio", { name: "To campus" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText("Date")).toHaveValue(tomorrow);
    expect(screen.getByLabelText("Departure time")).toHaveValue("07:45");
    expect(screen.getByRole("radio", { name: "3" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Starting area")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post trip" })).toBeDisabled();
  });

  it("posts what the contract needs, then shows the route and estimate", async () => {
    const departureAt = toSearchTime(tomorrow, "07:45")!;
    const fetchSpy = mockFetch(
      { status: 200, body: maya },
      NO_TRIPS,
      { status: 201, body: postedTrip("to_campus", departureAt, 3) },
      { status: 200, body: route },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    expect(screen.getByText("Osborne Village area")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText("Trip posted")).toBeInTheDocument();
    expect(await postedBody(fetchSpy)).toEqual({
      direction: "to_campus",
      place: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
      departureAt,
      seatsTotal: 3,
    });
    expect(screen.getByText("Osborne Village area → U of M Fort Garry Campus")).toBeInTheDocument();
    expect(screen.getByText("7:45 AM")).toBeInTheDocument();
    expect(screen.getByText("8:07 AM")).toBeInTheDocument();
    expect(screen.getByText("22 min · 14 km")).toBeInTheDocument();
    expect(await screen.findByText("route route")).toBeInTheDocument();
  });

  it("posts a trip from campus with the seats chosen", async () => {
    const departureAt = toSearchTime(tomorrow, "16:45")!;
    const fetchSpy = mockFetch(
      { status: 200, body: maya },
      NO_TRIPS,
      { status: 201, body: postedTrip("from_campus", departureAt, 5) },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("radio", { name: "From campus" }));
    expect(screen.getByText("Starting from")).toBeInTheDocument();
    expect(screen.getByText("Destination area")).toBeInTheDocument();
    expect(screen.getByLabelText("Departure time")).toHaveValue("16:45");

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("radio", { name: "5" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText("Trip posted")).toBeInTheDocument();
    expect(await postedBody(fetchSpy)).toMatchObject({ direction: "from_campus", departureAt, seatsTotal: 5 });
    expect(screen.getByText("U of M Fort Garry Campus → Osborne Village area")).toBeInTheDocument();
  });

  it("refuses a departure in the past without posting", async () => {
    const fetchSpy = mockFetch({ status: 200, body: maya });
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    const date = screen.getByLabelText("Date");
    await userEvent.clear(date);
    await userEvent.type(date, "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a departure time in the future.");
    expect(await postedBody(fetchSpy)).toBeUndefined();
  });

  it("refuses a starting point outside Winnipeg", async () => {
    mockFetch({ status: 200, body: maya });
    tapPoint = [-96.0, 50.5];
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));

    expect(screen.getByRole("alert")).toHaveTextContent("only covers Winnipeg");
    expect(screen.getByRole("button", { name: "Post trip" })).toBeDisabled();
  });

  it("says nothing was posted when the route can't be worked out", async () => {
    mockFetch(
      { status: 200, body: maya },
      NO_TRIPS,
      { status: 503, body: problem(503, "routing_unavailable", "The route couldn't be computed right now") },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText(/couldn't work out your route right now, so the trip wasn't posted/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post trip" })).toBeEnabled(); // they can try again
  });

  it("explains the API's departure_in_past error", async () => {
    mockFetch(
      { status: 200, body: maya },
      NO_TRIPS,
      {
        status: 422,
        body: problem(422, "departure_in_past", "The departure must be in the future", {
          errors: [{ field: "departureAt", message: "Must be in the future" }],
        }),
      },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText("Choose a departure time in the future.")).toBeInTheDocument();
  });

  it("warns about a trip already posted at that time, without posting", async () => {
    const existing = postedTrip("to_campus", toSearchTime(tomorrow, "07:30")!, 3); // arrives 7:52
    const fetchSpy = mockFetch({ status: 200, body: maya }, { status: 200, body: [existing] });
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" })); // 7:45, during that trip

    expect(await screen.findByText(/You already have a trip at 7:30 AM on .+\. Choose a different time\./)).toBeInTheDocument();
    expect(await postedBody(fetchSpy)).toBeUndefined();
  });

  it("allows a trip that doesn't clash, like the trip home later that day", async () => {
    const morning = postedTrip("to_campus", toSearchTime(tomorrow, "07:45")!, 3);
    const departureAt = toSearchTime(tomorrow, "16:45")!;
    const fetchSpy = mockFetch(
      { status: 200, body: maya },
      { status: 200, body: [morning] },
      { status: 201, body: postedTrip("from_campus", departureAt, 3) },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("radio", { name: "From campus" })); // 4:45 PM
    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText("Trip posted")).toBeInTheDocument();
    expect(await postedBody(fetchSpy)).toMatchObject({ direction: "from_campus", departureAt });
  });

  it("still posts if the student's trips can't be checked", async () => {
    const fetchSpy = mockFetch(
      { status: 200, body: maya },
      { status: 503, body: problem(503, "service_unavailable", "Unavailable") },
      { status: 201, body: postedTrip("to_campus", toSearchTime(tomorrow, "07:45")!, 3) },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

    expect(await screen.findByText("Trip posted")).toBeInTheDocument();
    expect(await postedBody(fetchSpy)).toBeDefined();
  });

  it("goes back to the form, with the same choices, to post another trip", async () => {
    mockFetch(
      { status: 200, body: maya },
      NO_TRIPS,
      { status: 201, body: postedTrip("to_campus", toSearchTime(tomorrow, "07:45")!, 3) },
      { status: 200, body: route },
    );
    renderWithProviders(<PostTrip />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: "Post trip" }));
    await userEvent.click(await screen.findByRole("button", { name: "Post another trip" }));

    expect(screen.getByRole("heading", { name: "Post a trip" })).toBeInTheDocument();
    expect(screen.getByText("Osborne Village area")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post trip" })).toBeEnabled();
  });

  describe("repeating on weekdays (#19)", () => {
    /** A Monday at least two days away, as a "2026-11-16" date. */
    function nextMonday(): string {
      const date = new Date();
      date.setDate(date.getDate() + 2);
      while (date.getDay() !== 1) date.setDate(date.getDate() + 1);
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    }

    const monday = nextMonday();

    /** Chooses an area, a Monday at 2 PM, and turns repeating on. */
    async function startRepeating() {
      await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
      const date = screen.getByLabelText("Date");
      await userEvent.clear(date);
      await userEvent.type(date, monday);
      const time = screen.getByLabelText("Departure time");
      await userEvent.clear(time);
      await userEvent.type(time, "14:00");
      await userEvent.click(screen.getByRole("switch", { name: "Repeat on weekdays" }));
    }

    function seriesResult(dates: string[], skippedDates: string[] = []) {
      return {
        seriesId: "series-1",
        trips: dates.map((date, i) => ({ ...postedTrip("to_campus", toSearchTime(date, "14:00")!, 3), id: `trip-${i + 1}`, seriesId: "series-1" })),
        skippedDates,
      };
    }

    it("starts from the first trip's day, for 4 weeks", async () => {
      mockFetch({ status: 200, body: maya });
      renderWithProviders(<PostTrip />);
      await startRepeating();

      expect(screen.getByRole("button", { name: "Monday" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByRole("button", { name: "Tuesday" })).toHaveAttribute("aria-pressed", "false");
      expect(screen.getByLabelText("Last day")).toHaveValue(addDays(monday, 28));
      expect(screen.getByText(`Every Mon at 2:00 PM, until ${formatDate(addDays(monday, 28))}. Up to 16 weeks.`)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Post repeating trip" })).toBeInTheDocument();
    });

    it("posts the chosen weekdays and last day, then says how many trips were made and which days were skipped", async () => {
      const wednesday = addDays(monday, 2);
      const fetchSpy = mockFetch(
        { status: 200, body: maya },
        { status: 201, body: seriesResult([monday, addDays(monday, 4), addDays(monday, 7)], [wednesday]) },
        { status: 200, body: route },
      );
      renderWithProviders(<PostTrip />);
      await startRepeating();
      await userEvent.click(screen.getByRole("button", { name: "Friday" }));
      await userEvent.click(screen.getByRole("button", { name: "Wednesday" }));
      const last = screen.getByLabelText("Last day");
      await userEvent.clear(last);
      await userEvent.type(last, addDays(monday, 11));
      await userEvent.click(screen.getByRole("button", { name: "Post repeating trip" }));

      expect(await screen.findByRole("heading", { name: "3 trips posted" })).toBeInTheDocument();
      const sent = fetchSpy.mock.calls.map(([input]) => input as Request).find((r) => r.method === "POST")!;
      expect(new URL(sent.url).pathname).toBe("/api/trips/series");
      expect(await sent.clone().json()).toEqual({
        direction: "to_campus",
        place: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
        departureAt: toSearchTime(monday, "14:00"),
        seatsTotal: 3,
        weekdays: ["mon", "wed", "fri"],
        endDate: addDays(monday, 11),
      });

      expect(screen.getByText("1 day skipped")).toBeInTheDocument();
      expect(within(screen.getByRole("list", { name: "Skipped days" })).getByText(formatDate(wednesday))).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "See them in My trips" })).toHaveAttribute("href", "/trips?role=driver");
    });

    it("says when every day clashed and nothing was posted", async () => {
      mockFetch({ status: 200, body: maya }, { status: 201, body: seriesResult([], [monday, addDays(monday, 7)]) });
      renderWithProviders(<PostTrip />);
      await startRepeating();
      await userEvent.click(screen.getByRole("button", { name: "Post repeating trip" }));

      expect(await screen.findByRole("heading", { name: "0 trips posted" })).toBeInTheDocument();
      expect(screen.getByText(/Every day clashes with a trip you already have/)).toBeInTheDocument();
      expect(screen.getByText("2 days skipped")).toBeInTheDocument();
    });

    it("asks for at least one day, without posting", async () => {
      const fetchSpy = mockFetch({ status: 200, body: maya });
      renderWithProviders(<PostTrip />);
      await startRepeating();
      await userEvent.click(screen.getByRole("button", { name: "Monday" }));
      await userEvent.click(screen.getByRole("button", { name: "Post repeating trip" }));

      expect(screen.getByRole("alert")).toHaveTextContent("Pick at least one day to repeat on.");
      expect(await postedBody(fetchSpy)).toBeUndefined();
    });

    it("asks for the first trip's day among the days (#315), without posting", async () => {
      const fetchSpy = mockFetch({ status: 200, body: maya });
      renderWithProviders(<PostTrip />);
      await startRepeating();
      await userEvent.click(screen.getByRole("button", { name: "Monday" }));
      await userEvent.click(screen.getByRole("button", { name: "Tuesday" }));
      await userEvent.click(screen.getByRole("button", { name: "Post repeating trip" }));

      expect(screen.getByRole("alert")).toHaveTextContent("Your first trip is on a Monday. Pick Monday too, or change the date.");
      expect(await postedBody(fetchSpy)).toBeUndefined();
    });

    it("refuses a last day more than 16 weeks away, without posting", async () => {
      const fetchSpy = mockFetch({ status: 200, body: maya });
      renderWithProviders(<PostTrip />);
      await startRepeating();
      const last = screen.getByLabelText("Last day");
      await userEvent.clear(last);
      await userEvent.type(last, addDays(monday, 16 * 7 + 1));
      await userEvent.click(screen.getByRole("button", { name: "Post repeating trip" }));

      expect(screen.getByRole("alert")).toHaveTextContent("A trip can repeat for up to 16 weeks.");
      expect(await postedBody(fetchSpy)).toBeUndefined();
    });

    it("turned off again, posts a one-off trip", async () => {
      const fetchSpy = mockFetch({ status: 200, body: maya }, NO_TRIPS, { status: 201, body: postedTrip("to_campus", toSearchTime(monday, "14:00")!, 3) });
      renderWithProviders(<PostTrip />);
      await startRepeating();
      await userEvent.click(screen.getByRole("switch", { name: "Repeat on weekdays" }));
      await userEvent.click(screen.getByRole("button", { name: "Post trip" }));

      expect(await screen.findByText("Trip posted")).toBeInTheDocument();
      const sent = fetchSpy.mock.calls.map(([input]) => input as Request).find((r) => r.method === "POST")!;
      expect(new URL(sent.url).pathname).toBe("/api/trips/");
    });
  });
});

