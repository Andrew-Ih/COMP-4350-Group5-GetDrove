import { screen } from "@testing-library/react";
import { Bell } from "lucide-react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders } from "@/shared/testing/render";

import { ComingSoon } from "./ComingSoon";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/notifications",
}));

const MAYA = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Chen", emailVerified: true };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ComingSoon", () => {
  it("says the screen is coming and in which sprint", () => {
    mockApi({ "/accounts/me": { status: 200, body: MAYA } });
    renderWithProviders(
      <ComingSoon title="Notifications" description="Updates go here." icon={<Bell />} sprint={2} />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByText("Coming in Sprint 2")).toBeInTheDocument();
    expect(screen.getByText("Updates go here.")).toBeInTheDocument();
  });

  it("keeps the signed-in header and offers a way back to finding a ride", async () => {
    mockApi({ "/accounts/me": { status: 200, body: MAYA } });
    renderWithProviders(
      <ComingSoon title="My trips" description="Trips go here." icon={<Bell />} sprint={2} />,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find a ride" })).toHaveAttribute("href", "/ride");
    expect(await screen.findByRole("button", { name: "Account" })).toBeInTheDocument();
  });
});
