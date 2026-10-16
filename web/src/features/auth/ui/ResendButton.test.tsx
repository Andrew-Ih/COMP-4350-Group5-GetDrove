import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch, renderWithProviders } from "@/shared/testing/render";

import { ResendButton } from "./ResendButton";

afterEach(() => vi.restoreAllMocks());

describe("ResendButton", () => {
  it("sends a new link, then waits a minute before allowing another", async () => {
    const fetchSpy = mockFetch({ status: 202, body: null });
    renderWithProviders(<ResendButton email="ada@myumanitoba.ca" />);

    await userEvent.click(screen.getByRole("button", { name: "Send a new link" }));

    expect(await screen.findByText(/We sent a new link/)).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /Send again in [01]:\d\d/ });
    expect(button).toBeDisabled();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("says so when the link couldn't be sent, and lets the student try again", async () => {
    mockFetch({ status: 503, body: "Service Unavailable" });
    renderWithProviders(<ResendButton email="ada@myumanitoba.ca" />);

    await userEvent.click(screen.getByRole("button", { name: "Send a new link" }));

    expect(await screen.findByText(/couldn't send it right now/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send a new link" })).toBeEnabled();
  });
});
