import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders } from "@/shared/testing/render";

import type { Notification } from "../model/notifications";
import { NotificationsPage } from "./NotificationsPage";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/notifications",
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

const note = (id: string, readAt: string | null): Notification => ({
  id,
  type: "driver_approved",
  title: `Notification ${id}`,
  body: "Your licence and insurance were approved.",
  tripId: null,
  requestId: null,
  createdAt: new Date(Date.now() - 60 * 60_000).toISOString(),
  readAt,
});

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
});

describe("NotificationsPage", () => {
  it("lists every notification with the unread count, and marks all as read", async () => {
    let allRead = false;
    const fetchSpy = mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/read-all": () => {
        allRead = true;
        return { status: 204 };
      },
      "/notifications/": () => ({
        status: 200,
        body: { items: [note("a", allRead ? "2026-10-15T00:00:00Z" : null), note("b", "2026-10-01T00:00:00Z")], unreadCount: allRead ? 0 : 1 },
      }),
    });
    renderWithProviders(<NotificationsPage />);

    expect(await screen.findByText("1 unread")).toBeInTheDocument();
    expect(screen.getByText("Notification a")).toBeInTheDocument();
    expect(screen.getByText("Notification b")).toBeInTheDocument();
    const listUrl = fetchSpy.mock.calls
      .map(([input]) => new URL(input instanceof Request ? input.url : String(input)))
      .find((url) => url.pathname.endsWith("/notifications/"))!;
    expect(listUrl.searchParams.get("limit")).toBe("50");

    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() => expect(screen.queryByText("1 unread")).not.toBeInTheDocument());
  });

  it("shows the newest 50, then up to 100 with Show more", async () => {
    const many = (n: number) => Array.from({ length: n }, (_, i) => note(`n${i}`, "2026-10-01T00:00:00Z"));
    const fetchSpy = mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/notifications/": (url) => ({ status: 200, body: { items: many(Number(url.searchParams.get("limit"))), unreadCount: 0 } }),
    });
    renderWithProviders(<NotificationsPage />);

    expect(await screen.findByText("Notification n49")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    expect(await screen.findByText("Notification n99")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
    expect(screen.getByText("Showing your latest 100 notifications.")).toBeInTheDocument();
    const limits = fetchSpy.mock.calls
      .map(([input]) => new URL(input instanceof Request ? input.url : String(input)))
      .filter((url) => url.pathname.endsWith("/notifications/"))
      .map((url) => url.searchParams.get("limit"));
    expect(limits).toEqual(expect.arrayContaining(["50", "100"]));
  });

  it("doesn't offer more when everything fits", async () => {
    mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/notifications/": { status: 200, body: { items: [note("a", null)], unreadCount: 1 } },
    });
    renderWithProviders(<NotificationsPage />);

    expect(await screen.findByText("Notification a")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("takes driver approval news to the approval page", async () => {
    mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/read": { status: 204 },
      "/notifications/": { status: 200, body: { items: [note("a", null)], unreadCount: 1 } },
    });
    renderWithProviders(<NotificationsPage />);

    await userEvent.click(await screen.findByRole("button", { name: /Notification a/ }));

    expect(push).toHaveBeenCalledWith("/account/driver");
  });
});
