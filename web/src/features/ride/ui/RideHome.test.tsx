import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LngLat } from "@/shared/map";
import { mockFetch, renderWithProviders } from "@/shared/testing/render";

import { fromQueryString } from "../model/search";
import { RideHome } from "./RideHome";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/ride",
}));

// The real map needs WebGL. This stand-in has a button that "taps" a point, like the map.
let tapPoint: LngLat = [-97.1438, 49.8768]; // Osborne Village
vi.mock("@/shared/map", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/shared/map")>();
  return {
    ...original,
    MapView: ({ onPick }: { onPick?: (p: LngLat) => void }) => (
      <button type="button" onClick={() => onPick?.(tapPoint)}>
        tap the map
      </button>
    ),
  };
});

const maya = {
  id: "1",
  email: "maya@myumanitoba.ca",
  firstName: "Maya",
  lastName: "Singh",
  emailVerified: true,
  roles: ["user"],
};

function mockLocation(result: { coords: { latitude: number; longitude: number } } | { code: number }) {
  const geolocation = {
    getCurrentPosition: vi.fn((ok: PositionCallback, fail: PositionErrorCallback) => {
      if ("coords" in result) ok(result as GeolocationPosition);
      else fail({ ...result, PERMISSION_DENIED: 1 } as GeolocationPositionError);
    }),
  };
  Object.defineProperty(navigator, "geolocation", { value: geolocation, configurable: true });
}

beforeEach(() => {
  push.mockReset();
  tapPoint = [-97.1438, 49.8768];
  mockFetch({ status: 200, body: maya });
});
afterEach(() => vi.restoreAllMocks());

describe("RideHome", () => {
  it("greets the student and waits for an area before searching", async () => {
    renderWithProviders(<RideHome />);

    expect(await screen.findByText(/, Maya$/)).toBeInTheDocument();
    expect(screen.getByText("Tap the map or use your location")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Find rides/ })).toBeDisabled();
  });

  it("names the tapped area and searches with what the contract needs", async () => {
    renderWithProviders(<RideHome />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    expect(screen.getByText("Osborne Village")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Find rides/ }));

    const url = push.mock.calls[0]?.[0] as string;
    expect(url.startsWith("/ride/results?")).toBe(true);
    const search = fromQueryString(new URLSearchParams(url.split("?")[1]));
    expect(search).toMatchObject({ lat: 49.8768, lng: -97.1438, direction: "to_campus" });
    expect(Date.parse(search!.time)).toBeGreaterThan(Date.now());
  });

  it("uses the device's location when asked", async () => {
    mockLocation({ coords: { latitude: 49.8775, longitude: -97.172 } }); // Wolseley
    renderWithProviders(<RideHome />);

    await userEvent.click(screen.getByRole("button", { name: "Use my location" }));

    expect(screen.getByText("Wolseley")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Find rides/ })).toBeEnabled();
  });

  it("explains what to do when location is turned off", async () => {
    mockLocation({ code: 1 });
    renderWithProviders(<RideHome />);

    await userEvent.click(screen.getByRole("button", { name: "Use my location" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Tap the map to choose your area instead.");
  });

  it("refuses areas outside Winnipeg", async () => {
    tapPoint = [-97.4, 49.2];
    renderWithProviders(<RideHome />);

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));

    expect(screen.getByRole("alert")).toHaveTextContent("only covers Winnipeg");
    expect(screen.getByRole("button", { name: /Find rides/ })).toBeDisabled();
  });

  it("switches to leaving campus: 'Leave after', and the area becomes the drop-off", async () => {
    renderWithProviders(<RideHome />);

    await userEvent.click(screen.getByRole("radio", { name: "From campus" }));

    expect(screen.getByRole("radio", { name: "From campus" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText("Leave after")).toHaveAttribute("type", "time");
    expect(screen.getByText("Drop-off area")).toBeInTheDocument();
    expect(screen.getByText("Leaving from")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));
    await userEvent.click(screen.getByRole("button", { name: /Find rides/ }));
    const url = push.mock.calls[0]?.[0] as string;
    expect(fromQueryString(new URLSearchParams(url.split("?")[1]))?.direction).toBe("from_campus");
  });

  it("refuses a time in the past", async () => {
    renderWithProviders(<RideHome />);
    await userEvent.click(screen.getByRole("button", { name: "tap the map" }));

    const date = screen.getByLabelText("Date");
    await userEvent.clear(date);
    await userEvent.type(date, "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: /Find rides/ }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a time in the future.");
    expect(push).not.toHaveBeenCalled();
  });
});
