import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders } from "@/shared/testing/render";

import { AddCard } from "./AddCard";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/account/card",
}));

// No Stripe key configured (and no mock API).
vi.mock("@/shared/config/env", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/config/env")>()),
  stripePublishableKey: "",
  apiMocking: false,
}));

afterEach(() => vi.restoreAllMocks());

describe("AddCard without a Stripe key", () => {
  it("says adding a card isn't set up, instead of showing a form that can't work", async () => {
    mockApi({ "/payments/methods": { status: 200, body: [] }, "/accounts/me": { status: 200, body: { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] } } });
    renderWithProviders(<AddCard next={undefined} />);

    expect(await screen.findByText("Adding a card isn't set up on this site yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save card" })).not.toBeInTheDocument();
  });
});
