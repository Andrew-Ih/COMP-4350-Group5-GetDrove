import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAccessToken, setAccessToken } from "@/shared/api";
import { mockFetch, problem, renderWithProviders } from "@/shared/testing/render";

import { LoginForm } from "./LoginForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

async function logIn(email = "ada@myumanitoba.ca", password = "correct horse") {
  if (email) await userEvent.type(screen.getByLabelText("UofM email"), email);
  if (password) await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
}

beforeEach(() => push.mockReset());
afterEach(() => {
  setAccessToken(undefined);
  vi.restoreAllMocks();
});

describe("LoginForm", () => {
  it("logs in, keeps the token in memory and goes to the requested page", async () => {
    const fetchSpy = mockFetch({ status: 200, body: { accessToken: "tok", tokenType: "Bearer", expiresIn: 900 } });
    renderWithProviders(<LoginForm next="/trips" />);

    await logIn();

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/trips"));
    expect(getAccessToken()).toBe("tok");
    const request = fetchSpy.mock.calls[0]?.[0] as Request;
    expect(request.url).toMatch(/\/accounts\/auth\/login$/);
    expect(await request.json()).toEqual({ email: "ada@myumanitoba.ca", password: "correct horse" });
  });

  it("never follows a link to another site after logging in", async () => {
    mockFetch({ status: 200, body: { accessToken: "tok", tokenType: "Bearer", expiresIn: 900 } });
    renderWithProviders(<LoginForm next="https://evil.example" />);

    await logIn();

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("shows one message for a wrong email or password", async () => {
    mockFetch({ status: 401, body: problem(401, "invalid_credentials", "Wrong email or password") });
    renderWithProviders(<LoginForm />);

    await logIn();

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
    expect(push).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeUndefined();
  });

  it("asks an unverified student to verify, and can send a new link", async () => {
    const fetchSpy = mockFetch(
      { status: 403, body: problem(403, "email_not_verified", "Verify your email first") },
      { status: 202, body: null },
    );
    renderWithProviders(<LoginForm />);

    await logIn();
    expect(await screen.findByText("Verify your email first")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send a new link" }));

    expect(await screen.findByText(/We sent a new link/)).toBeInTheDocument();
    const resendRequest = fetchSpy.mock.calls[1]?.[0] as Request;
    expect(resendRequest.url).toMatch(/\/auth\/resend-verification$/);
    expect(await resendRequest.json()).toEqual({ email: "ada@myumanitoba.ca" });
  });

  it("checks the fields before sending anything", async () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<LoginForm />);

    await logIn("ada@gmail.com", "");

    expect(await screen.findByText("Use your @myumanitoba.ca email.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
