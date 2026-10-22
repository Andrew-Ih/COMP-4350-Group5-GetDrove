import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { endSession, getAccessToken, setAccessToken } from "@/shared/api";
import { mockFetch, renderWithProviders } from "@/shared/testing/render";

import { AppHeader } from "./AppHeader";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/drive/trip/requests",
  useRouter: () => ({ replace, push: vi.fn() }),
}));

afterEach(() => {
  endSession();
  replace.mockReset();
  vi.restoreAllMocks();
});

describe("AppHeader", () => {
  it("marks the section of the current page as active", () => {
    renderWithProviders(<AppHeader userName="Priya" />);
    const [desktopNav] = screen.getAllByRole("navigation", { name: "Main" });
    expect(desktopNav).toBeDefined();
    expect(screen.getAllByRole("link", { name: "Drive" })[0]).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { name: "Ride" })[0]).not.toHaveAttribute("aria-current");
  });

  it("opens and closes the mobile menu", async () => {
    renderWithProviders(<AppHeader userName="Priya" />);
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("link", { name: "My trips" })).toHaveLength(2);
  });

  it("links the bell to notifications", () => {
    renderWithProviders(<AppHeader userName="Priya" />);

    const bell = screen.getByRole("link", { name: "Notifications" });
    expect(bell).toHaveAttribute("href", "/notifications");
    expect(bell).not.toHaveAttribute("aria-current");
  });

  it("logs out from the account menu", async () => {
    const fetchSpy = mockFetch({ status: 204 });
    setAccessToken("tok");
    renderWithProviders(<AppHeader userName="Priya" />);

    await userEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByText("Logged in as Priya")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "Log out" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(String(fetchSpy.mock.calls[0]?.[0])).toContain("/accounts/auth/logout");
    expect(getAccessToken()).toBeUndefined();
  });

  it("logs out from the mobile menu too", async () => {
    mockFetch({ status: 204 });
    renderWithProviders(<AppHeader userName="Priya" />);

    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("closes the account menu when clicking elsewhere", async () => {
    renderWithProviders(<AppHeader userName="Priya" />);

    await userEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.click(document.body);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
