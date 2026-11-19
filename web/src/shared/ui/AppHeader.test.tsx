import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { endSession, getAccessToken, setAccessToken } from "@/shared/api";
import { mockFetch, renderWithProviders } from "@/shared/testing/render";

import { AppHeader } from "./AppHeader";
import { HeaderBellContext } from "./HeaderBell";

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

  it("links to the payment card, driver status and auto-accept from the account menu", async () => {
    renderWithProviders(<AppHeader userName="Priya" />);

    await userEvent.click(screen.getByRole("button", { name: "Account" }));

    expect(screen.getByRole("menuitem", { name: "Payment card" })).toHaveAttribute("href", "/account/card");
    expect(screen.getByRole("menuitem", { name: "Driver status" })).toHaveAttribute("href", "/account/driver");
    expect(screen.getByRole("menuitem", { name: "Auto-accept" })).toHaveAttribute("href", "/account/auto-accept");
  });

  it("links admins to the driver applications", async () => {
    renderWithProviders(<AppHeader userName="Priya" isAdmin />);

    await userEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("menuitem", { name: "Driver applications" })).toHaveAttribute("href", "/admin/drivers");

    // Opening the mobile menu closes the account menu, so only the mobile link is left.
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("link", { name: "Driver applications" })).toHaveAttribute("href", "/admin/drivers");
  });

  it("doesn't show the driver applications to other students", async () => {
    renderWithProviders(<AppHeader userName="Priya" />);

    await userEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("menuitem", { name: "Payment card" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Driver applications" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.queryByRole("link", { name: "Driver applications" })).not.toBeInTheDocument();
  });

  it("shows the app's notification bell when it's given one", () => {
    renderWithProviders(
      <HeaderBellContext.Provider value={<button type="button">the real bell</button>}>
        <AppHeader userName="Priya" />
      </HeaderBellContext.Provider>,
    );

    expect(screen.getByRole("button", { name: "the real bell" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Notifications" })).not.toBeInTheDocument();
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
