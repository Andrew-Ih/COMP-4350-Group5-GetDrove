import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { DriverProfile } from "../model/driver";
import { DriverGate } from "./DriverGate";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/drive/new",
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };

const profile = (status: DriverProfile["status"]): DriverProfile => ({
  status,
  rejectionReason: status === "rejected" ? "The licence photo is blurry." : null,
  documents: { licence: status !== "none", insurance: status !== "none" },
  vehicle: null,
  submittedAt: null,
  reviewedAt: null,
});

function render(answer: { status: number; body: unknown }) {
  mockApi({ "/accounts/me": { status: 200, body: maya }, "/me/driver": answer });
  renderWithProviders(
    <DriverGate>
      <p>the Post a trip form</p>
    </DriverGate>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("DriverGate", () => {
  it("shows Post a trip to an approved driver", async () => {
    render({ status: 200, body: profile("approved") });
    expect(await screen.findByText("the Post a trip form")).toBeInTheDocument();
  });

  it("tells a student who hasn't applied why they can't post, with a way to apply", async () => {
    render({ status: 200, body: profile("none") });

    expect(await screen.findByRole("heading", { name: "Get approved to drive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Apply to drive" })).toHaveAttribute("href", "/account/driver");
    expect(screen.queryByText("the Post a trip form")).not.toBeInTheDocument();
  });

  it("tells a pending applicant they're waiting", async () => {
    render({ status: 200, body: profile("pending") });

    expect(await screen.findByText("We're checking your documents")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See your application" })).toBeInTheDocument();
  });

  it("shows a rejected applicant the reason", async () => {
    render({ status: 200, body: profile("rejected") });

    expect(await screen.findByText("The licence photo is blurry.")).toBeInTheDocument();
  });

  it("shows the form if the status can't be loaded (the API still refuses unapproved drivers)", async () => {
    render({ status: 500, body: problem(500, "unexpected_error", "Something went wrong") });
    expect(await screen.findByText("the Post a trip form")).toBeInTheDocument();
  });
});
