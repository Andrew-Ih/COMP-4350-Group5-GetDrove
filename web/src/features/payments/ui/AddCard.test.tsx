import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { CardError, PaymentMethod } from "../model/card";
import { AddCard } from "./AddCard";
import type { CardFieldProps } from "./cardField";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/account/card",
}));

vi.mock("@/shared/config/env", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/config/env")>()),
  stripePublishableKey: "pk_test_example",
  apiMocking: false,
}));

// Stripe's form can't run in tests. This stand-in fills in the card and answers the
// confirmation with whatever the test sets in `stripe.result`.
const stripe = vi.hoisted(() => ({ result: {} as { error?: CardError }, confirmedWith: [] as string[] }));
vi.mock("./StripeCardField", () => ({
  StripeCardField: ({ confirmRef, onChange }: CardFieldProps) => {
    confirmRef.current = async (clientSecret) => {
      stripe.confirmedWith.push(clientSecret);
      return stripe.result;
    };
    return (
      <button type="button" onClick={() => onChange({ complete: true })}>
        fill in the card
      </button>
    );
  },
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };
const visa: PaymentMethod = { id: "pm_1", brand: "visa", last4: "4242", expMonth: 12, expYear: 2030, isDefault: true };

type Answer = { status: number; body?: unknown };

/** Answers in order, repeating the last one: the cards before and after saving one. */
function inTurn(...answers: Answer[]) {
  let i = 0;
  return () => answers[Math.min(i++, answers.length - 1)]!;
}

function api(methods: Answer[] = [{ status: 200, body: [] }], setupIntent: Answer = { status: 201, body: { clientSecret: "seti_123_secret_abc" } }) {
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    "/payments/methods": inTurn(...methods),
    "/payments/setup-intent": setupIntent,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  stripe.result = {};
  stripe.confirmedWith = [];
});

describe("AddCard", () => {
  it("saves a card with Stripe and shows it", async () => {
    api([{ status: 200, body: [] }, { status: 200, body: [visa] }]);
    renderWithProviders(<AddCard next={undefined} />);

    expect(await screen.findByRole("heading", { name: "Add a card" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save card" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "fill in the card" }));
    await userEvent.click(screen.getByRole("button", { name: "Save card" }));

    expect(await screen.findByText("Card saved")).toBeInTheDocument();
    expect(stripe.confirmedWith).toEqual(["seti_123_secret_abc"]);
    expect(screen.getByText("Visa ending in 4242")).toBeInTheDocument();
    expect(screen.getByText("Expires 12/30")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find a ride" })).toHaveAttribute("href", "/ride");
  });

  it("goes back to the trip the student came from", async () => {
    api([{ status: 200, body: [] }, { status: 200, body: [visa] }]);
    renderWithProviders(<AddCard next="/ride/trip/t1?lat=49.87&lng=-97.14" />);

    await userEvent.click(await screen.findByRole("button", { name: "fill in the card" }));
    await userEvent.click(screen.getByRole("button", { name: "Save card" }));

    expect(await screen.findByRole("link", { name: "Back to your trip" })).toHaveAttribute("href", "/ride/trip/t1?lat=49.87&lng=-97.14");
  });

  it("explains a declined card and keeps the form", async () => {
    stripe.result = { error: { code: "card_declined", declineCode: "generic_decline", message: "Your card was declined." } };
    api();
    renderWithProviders(<AddCard next={undefined} />);

    await userEvent.click(await screen.findByRole("button", { name: "fill in the card" }));
    await userEvent.click(screen.getByRole("button", { name: "Save card" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your card was declined. Try a different card.");
    expect(screen.queryByText("Card saved")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save card" })).toBeEnabled();
  });

  it("says when card payments are unavailable", async () => {
    api(undefined, { status: 503, body: problem(503, "payments_unavailable", "Stripe can't be reached right now") });
    renderWithProviders(<AddCard next={undefined} />);

    await userEvent.click(await screen.findByRole("button", { name: "fill in the card" }));
    await userEvent.click(screen.getByRole("button", { name: "Save card" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Card payments are unavailable right now");
    expect(stripe.confirmedWith).toEqual([]);
  });

  it("shows the saved card, and lets the student add a different one or keep it", async () => {
    api([{ status: 200, body: [visa] }]);
    renderWithProviders(<AddCard next={undefined} />);

    expect(await screen.findByText("Visa ending in 4242")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save card" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Use a different card" }));
    expect(screen.getByRole("heading", { name: "Add a different card" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Keep my current card" }));
    expect(screen.getByText("Visa ending in 4242")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add a different card" })).not.toBeInTheDocument();
  });

  it("offers to try again when the cards can't be loaded", async () => {
    api([{ status: 503, body: problem(503, "payments_unavailable", "Stripe can't be reached right now") }, { status: 200, body: [] }]);
    renderWithProviders(<AddCard next={undefined} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Card payments are unavailable right now");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Add a card" })).toBeInTheDocument());
  });

  it("asks the student to log in again when their session has ended", async () => {
    api([{ status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") }]);
    renderWithProviders(<AddCard next={undefined} />);

    expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login?next=%2Faccount%2Fcard");
  });
});
