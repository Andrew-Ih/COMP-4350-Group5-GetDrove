import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { Notification } from "../model/notifications";
import { NotificationBell } from "./NotificationBell";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/ride",
}));

const note = (id: string, changes: Partial<Notification> = {}): Notification => ({
  id,
  type: "request_accepted",
  title: "Request accepted",
  body: "Priya accepted your request for tomorrow at 7:52 AM.",
  tripId: "t1",
  requestId: "r1",
  createdAt: new Date(Date.now() - 4 * 60_000).toISOString(),
  readAt: null,
  ...changes,
});

const ITEMS = [
  note("n1"),
  note("n2", { type: "seat_requested", title: "New seat request", body: "Amara asked for a seat.", tripId: "t2" }),
  note("n3", { title: "Request declined", readAt: new Date().toISOString() }),
];

type Answer = { status: number; body?: unknown };

/** The API for these tests: marking read works like the real one, so a refetch keeps it. */
function api(list?: Answer) {
  const read = new Set(ITEMS.filter((n) => n.readAt).map((n) => n.id));
  const current = () => {
    const items = ITEMS.map((n) => (read.has(n.id) ? { ...n, readAt: n.readAt ?? new Date().toISOString() } : n));
    return { status: 200, body: { items, unreadCount: items.filter((n) => !n.readAt).length } };
  };
  return mockApi({
    "/notifications/read-all": () => {
      for (const n of ITEMS) read.add(n.id);
      return { status: 204 };
    },
    "/read": (url) => {
      read.add(url.pathname.split("/").at(-2)!);
      return { status: 204 };
    },
    "/notifications/": list ? () => list : current,
  });
}

const calls = (fetchSpy: ReturnType<typeof api>, path: string) =>
  fetchSpy.mock.calls.filter(([input]) => new URL(input instanceof Request ? input.url : String(input)).pathname.endsWith(path));

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
});

describe("NotificationBell", () => {
  it("shows how many are unread", async () => {
    api();
    renderWithProviders(<NotificationBell />);

    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toHaveTextContent("2");
  });

  it("has no count when everything is read", async () => {
    api({ status: 200, body: { items: [], unreadCount: 0 } });
    renderWithProviders(<NotificationBell />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Notifications" })).not.toHaveTextContent(/\d/);
  });

  it("opens a panel with the latest notifications, unread ones marked", async () => {
    api();
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));

    const panel = screen.getByRole("dialog", { name: "Notifications" });
    const rows = await within(panel).findAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Request accepted");
    expect(rows[0]).toHaveTextContent("4 min ago");
    expect(rows[0]).toHaveTextContent("Unread");
    expect(rows[2]).not.toHaveTextContent("Unread");
    expect(within(panel).getByRole("link", { name: "See all" })).toHaveAttribute("href", "/notifications");
  });

  it("marks a notification read and goes to the trip it's about", async () => {
    const fetchSpy = api();
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await userEvent.click(await screen.findByRole("button", { name: /New seat request/ }));

    expect(push).toHaveBeenCalledWith("/drive/trips/t2");
    await waitFor(() => expect(calls(fetchSpy, "/notifications/n2/read")).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("doesn't mark an already read notification again", async () => {
    const fetchSpy = api();
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await userEvent.click(await screen.findByRole("button", { name: /Request declined/ }));

    expect(push).toHaveBeenCalledWith("/ride/trip/t1");
    expect(calls(fetchSpy, "/read")).toHaveLength(0);
  });

  it("marks all as read", async () => {
    const fetchSpy = api();
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));

    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(calls(fetchSpy, "/read-all")).toHaveLength(1);
  });

  it("says when there are none yet", async () => {
    api({ status: 200, body: { items: [], unreadCount: 0 } });
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications" }));

    expect(await screen.findByText(/No notifications yet/)).toBeInTheDocument();
  });

  it("offers to try again when they can't be loaded", async () => {
    api({ status: 500, body: problem(500, "unexpected_error", "Something went wrong") });
    renderWithProviders(<NotificationBell />);

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load your notifications.");
  });

  it("closes with Escape", async () => {
    api();
    renderWithProviders(<NotificationBell />);

    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
