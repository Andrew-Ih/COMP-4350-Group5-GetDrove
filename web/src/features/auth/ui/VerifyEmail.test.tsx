import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch, problem, renderWithProviders } from "@/shared/testing/render";

import { VerifyEmail } from "./VerifyEmail";

afterEach(() => vi.restoreAllMocks());

describe("VerifyEmail", () => {
  it("sends the token once and confirms the account", async () => {
    const fetchSpy = mockFetch({ status: 204 });
    renderWithProviders(<VerifyEmail token="abc123" />);

    expect(await screen.findByRole("heading", { name: "You're verified" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(await (fetchSpy.mock.calls[0]?.[0] as Request).json()).toEqual({ token: "abc123" });
  });

  it("offers a new link when the old one has expired", async () => {
    mockFetch(
      { status: 410, body: problem(410, "token_expired", "This link has expired") },
      { status: 202, body: null },
    );
    renderWithProviders(<VerifyEmail token="old" />);

    expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("UofM email"), "ada@myumanitoba.ca");
    await userEvent.click(screen.getByRole("button", { name: "Send a new link" }));

    expect(await screen.findByText(/a new link is on its way/)).toBeInTheDocument();
  });

  it("explains a used link and points to log in", async () => {
    mockFetch({ status: 400, body: problem(400, "invalid_token", "This link is not valid") });
    renderWithProviders(<VerifyEmail token="used" />);

    expect(await screen.findByRole("heading", { name: "This link doesn't work" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toBeInTheDocument();
  });

  it("asks for a new link when there's no token, without calling the API", () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<VerifyEmail token={undefined} />);

    expect(screen.getByRole("heading", { name: "This link is incomplete" })).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
