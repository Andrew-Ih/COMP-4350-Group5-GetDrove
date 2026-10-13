import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppHeader } from "./AppHeader";

vi.mock("next/navigation", () => ({ usePathname: () => "/drive/trip/requests" }));

describe("AppHeader", () => {
  it("marks the section of the current page as active", () => {
    render(<AppHeader userName="Priya" />);
    const [desktopNav] = screen.getAllByRole("navigation", { name: "Main" });
    expect(desktopNav).toBeDefined();
    expect(screen.getAllByRole("link", { name: "Drive" })[0]).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { name: "Ride" })[0]).not.toHaveAttribute("aria-current");
  });

  it("opens and closes the mobile menu", async () => {
    render(<AppHeader userName="Priya" />);
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("link", { name: "My trips" })).toHaveLength(2);
  });
});
