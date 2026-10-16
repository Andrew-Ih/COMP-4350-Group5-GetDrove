import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch, problem, renderWithProviders } from "@/shared/testing/render";

import { SignupForm } from "./SignupForm";

async function fillIn(overrides: Partial<Record<string, string>> = {}) {
  const values = {
    "First name": "Ada",
    "Last name": "Lovelace",
    "UofM email": "ada@myumanitoba.ca",
    Password: "correct horse",
    ...overrides,
  };
  for (const [label, value] of Object.entries(values)) {
    if (value) await userEvent.type(screen.getByLabelText(label), value);
  }
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
}

afterEach(() => vi.restoreAllMocks());

describe("SignupForm", () => {
  it("sends the contract's fields and then asks the student to check their email", async () => {
    const fetchSpy = mockFetch({ status: 201, body: { id: "1", email: "ada@myumanitoba.ca", emailVerified: false } });
    renderWithProviders(<SignupForm />);

    await fillIn();

    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText("ada@myumanitoba.ca")).toBeInTheDocument();
    const request = fetchSpy.mock.calls[0]?.[0] as Request;
    expect(request.url).toMatch(/\/accounts\/auth\/signup$/);
    expect(await request.json()).toEqual({
      firstName: "Ada",
      lastName: "Lovelace",
      email: "ada@myumanitoba.ca",
      password: "correct horse",
    });
  });

  it("rejects a non-UofM email before sending anything", async () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<SignupForm />);

    await fillIn({ "UofM email": "ada@gmail.com" });

    expect(await screen.findByText("Use your @myumanitoba.ca email.")).toBeInTheDocument();
    expect(screen.getByLabelText("UofM email")).toHaveAttribute("aria-invalid", "true");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("needs a password of at least 10 characters", async () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<SignupForm />);

    await fillIn({ Password: "short" });

    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows a taken email under the email field, with a way to log in", async () => {
    mockFetch({ status: 409, body: problem(409, "email_taken", "An account with this email already exists") });
    renderWithProviders(<SignupForm />);

    await fillIn();

    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in instead" })).toHaveAttribute("href", "/login");
  });

  it("puts the server's field errors on the right fields", async () => {
    mockFetch({
      status: 422,
      body: problem(422, "invalid_input", "Check the highlighted fields.", {
        errors: [{ field: "lastName", message: "String should have at most 50 characters" }],
      }),
    });
    renderWithProviders(<SignupForm />);

    await fillIn();

    expect(await screen.findByText("String should have at most 50 characters")).toBeInTheDocument();
    expect(screen.getByLabelText("Last name")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows a message when the service is down", async () => {
    mockFetch({ status: 503, body: "Service Unavailable" });
    renderWithProviders(<SignupForm />);

    await fillIn();

    expect(await screen.findByRole("alert")).toHaveTextContent("The service is unavailable");
  });
});
