import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch, OFFLINE, problem, renderWithProviders } from "@/shared/testing/render";

import { NOT_FOUND_MESSAGE, TOO_SHORT_MESSAGE } from "../model/places";
import { AddressSearch } from "./AddressSearch";

const osborne = { label: "750 Osborne Street, Fort Rouge", lat: 49.8664, lng: -97.1386 };
const forks = { label: "The Forks, Downtown", lat: 49.8875, lng: -97.1306 };

afterEach(() => vi.restoreAllMocks());

async function search(text: string) {
  await userEvent.type(screen.getByRole("searchbox", { name: "Address or place" }), text);
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
}

describe("AddressSearch", () => {
  it("looks up what was typed only when Search is pressed, then picks a match like a tap", async () => {
    const fetchSpy = mockFetch({ status: 200, body: { places: [osborne, forks] } });
    const onPick = vi.fn();
    renderWithProviders(<AddressSearch onPick={onPick} />);

    await userEvent.type(screen.getByRole("searchbox", { name: "Address or place" }), " 750 Osborne St ");
    expect(fetchSpy).not.toHaveBeenCalled(); // nothing while typing
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    const request = fetchSpy.mock.calls[0]![0] as Request;
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/routing/places");
    expect(new URL(request.url).search).toBe(""); // never in the URL
    expect(await request.json()).toEqual({ query: "750 Osborne St" });

    const matches = await screen.findByRole("list", { name: "Matching places" });
    expect(matches).toHaveTextContent("750 Osborne Street, Fort Rouge");
    expect(screen.getByRole("link", { name: "OpenStreetMap" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "The Forks, Downtown" }));

    expect(onPick).toHaveBeenCalledWith([-97.1306, 49.8875]);
    expect(screen.queryByRole("list", { name: "Matching places" })).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Address or place" })).toHaveValue(""); // not kept
  });

  it("pressing Enter searches too", async () => {
    const fetchSpy = mockFetch({ status: 200, body: { places: [osborne] } });
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await userEvent.type(screen.getByRole("searchbox", { name: "Address or place" }), "750 Osborne{Enter}");

    expect(await screen.findByRole("button", { name: osborne.label })).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("asks for more than a couple of letters, without looking anything up", async () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await search("ab");

    expect(screen.getByRole("status")).toHaveTextContent(TOO_SHORT_MESSAGE);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("says when nothing in Winnipeg matched, and that the map still works", async () => {
    mockFetch({ status: 200, body: { places: [] } });
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await search("123 Nowhere Rd");

    expect(await screen.findByText(NOT_FOUND_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Matching places" })).not.toBeInTheDocument();
  });

  it("says when the lookup is down", async () => {
    mockFetch({ status: 503, body: problem(503, "geocoding_unavailable", "Down") });
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await search("750 Osborne St");

    expect(await screen.findByText(/can't look up addresses right now/)).toBeInTheDocument();
  });

  it("says when offline", async () => {
    mockFetch(OFFLINE);
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await search("750 Osborne St");

    expect(await screen.findByText("Check your connection and try again.")).toBeInTheDocument();
  });

  it("clears the message when the student types again", async () => {
    mockFetch({ status: 200, body: { places: [] } });
    renderWithProviders(<AddressSearch onPick={vi.fn()} />);

    await search("123 Nowhere Rd");
    await screen.findByText(NOT_FOUND_MESSAGE);
    await userEvent.type(screen.getByRole("searchbox", { name: "Address or place" }), "x");

    expect(screen.queryByText(NOT_FOUND_MESSAGE)).not.toBeInTheDocument();
  });
});
