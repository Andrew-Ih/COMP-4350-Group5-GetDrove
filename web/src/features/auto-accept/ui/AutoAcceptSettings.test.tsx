import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { problem, renderWithProviders } from "@/shared/testing/render";

import type { AutoAcceptRules } from "../model/rules";
import { AutoAcceptSettings } from "./AutoAcceptSettings";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/account/auto-accept",
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };
const DEFAULTS: AutoAcceptRules = { enabled: false, maxDetourMinutes: 5, minRating: null };

type Answer = { status: number; body?: unknown };

/** Fakes the API: the student, the saved rules, and what saving answers (by default, what was sent). */
function api(rules: Answer = { status: 200, body: DEFAULTS }, save?: Answer) {
  const sent: unknown[] = [];
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const request = input as Request;
    const path = new URL(request.url).pathname;
    let answer: Answer = { status: 500, body: problem(500, "unexpected_error", `No fake for ${path}`) };
    if (path.endsWith("/accounts/me")) answer = { status: 200, body: maya };
    else if (path.endsWith("/auto-accept") && request.method === "GET") answer = rules;
    else if (path.endsWith("/auto-accept") && request.method === "PUT") {
      const body: unknown = await request.clone().json();
      sent.push(body);
      answer = save ?? { status: 200, body };
    }
    return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
      status: answer.status,
      headers: { "Content-Type": answer.status >= 400 ? "application/problem+json" : "application/json" },
    });
  });
  return { spy, sent };
}

const gets = (spy: ReturnType<typeof api>["spy"]) =>
  spy.mock.calls.filter(([input]) => (input as Request).method === "GET" && (input as Request).url.endsWith("/auto-accept")).length;

afterEach(() => vi.restoreAllMocks());

describe("AutoAcceptSettings", () => {
  it("shows the saved rules: off by default, with nothing to save yet", async () => {
    api();
    renderWithProviders(<AutoAcceptSettings />);

    expect(screen.getByText("Loading your rules…")).toBeInTheDocument();
    const toggle = await screen.findByRole("switch", { name: "Accept requests automatically" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByLabelText("Longest detour for a pickup")).not.toBeInTheDocument();
    expect(screen.getByText(/Every request waits for you to accept or decline it\./)).toBeInTheDocument();
    expect(screen.getByText(/Changes apply to new requests only/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("turns it on with a detour and a rating, and saves", async () => {
    const { sent } = api();
    renderWithProviders(<AutoAcceptSettings />);

    await userEvent.click(await screen.findByRole("switch", { name: "Accept requests automatically" }));
    const detour = screen.getByLabelText("Longest detour for a pickup");
    expect(detour).toHaveValue(5);
    await userEvent.clear(detour);
    await userEvent.type(detour, "8");
    await userEvent.click(screen.getByRole("radio", { name: "★ 4.0+" }));
    expect(screen.getByText(/New riders without ratings always pass/)).toBeInTheDocument();
    expect(screen.getByText(/add at most 8 min, from riders rated 4\.0 or higher/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(sent).toEqual([{ enabled: true, maxDetourMinutes: 8, minRating: 4 }]);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("turns it off, keeping the values", async () => {
    const { sent } = api({ status: 200, body: { enabled: true, maxDetourMinutes: 10, minRating: 4.5 } });
    renderWithProviders(<AutoAcceptSettings />);

    expect(await screen.findByLabelText("Longest detour for a pickup")).toHaveValue(10);
    expect(screen.getByRole("radio", { name: "★ 4.5+" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("switch", { name: "Accept requests automatically" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(sent).toEqual([{ enabled: false, maxDetourMinutes: 10, minRating: 4.5 }]);
  });

  it("shows a saved rating that isn't one of the usual ones", async () => {
    api({ status: 200, body: { enabled: true, maxDetourMinutes: 5, minRating: 4.2 } });
    renderWithProviders(<AutoAcceptSettings />);

    expect(await screen.findByRole("radio", { name: "★ 4.2+" })).toHaveAttribute("aria-checked", "true");
  });

  it.each(["31", "-1", "2.5", ""])("refuses a detour of %j without saving", async (value) => {
    const { sent } = api({ status: 200, body: { enabled: true, maxDetourMinutes: 5, minRating: null } });
    renderWithProviders(<AutoAcceptSettings />);

    const detour = await screen.findByLabelText("Longest detour for a pickup");
    await userEvent.clear(detour);
    if (value) await userEvent.type(detour, value);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter a whole number of minutes from 0 to 30.");
    expect(detour).toHaveAttribute("aria-invalid", "true");
    expect(sent).toEqual([]);
  });

  it("shows the API's 422 on the field it's about", async () => {
    api(undefined, { status: 422, body: problem(422, "invalid_input", "Invalid input", { errors: [{ field: "minRating", message: "Must be from 1 to 5" }] }) });
    renderWithProviders(<AutoAcceptSettings />);

    await userEvent.click(await screen.findByRole("switch", { name: "Accept requests automatically" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Choose a rating from 1 to 5, or any rating.")).toBeInTheDocument();
  });

  it("says when saving fails", async () => {
    api(undefined, { status: 503, body: problem(503, "service_unavailable", "Unavailable") });
    renderWithProviders(<AutoAcceptSettings />);
    await userEvent.click(await screen.findByRole("switch", { name: "Accept requests automatically" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/We couldn't save your rules/)).toBeInTheDocument();
  });

  it("asks to log in again when saving after the session ended", async () => {
    api(undefined, { status: 401, body: problem(401, "unauthorized", "Missing or invalid access token") });
    renderWithProviders(<AutoAcceptSettings />);
    await userEvent.click(await screen.findByRole("switch", { name: "Accept requests automatically" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/Your session has ended/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login?next=%2Faccount%2Fauto-accept");
  });

  it("offers to try again when the rules can't be loaded", async () => {
    const { spy } = api({ status: 500, body: problem(500, "unexpected_error", "Something went wrong") });
    renderWithProviders(<AutoAcceptSettings />);

    expect(await screen.findByText("We couldn't load your rules")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(gets(spy)).toBe(2);
  });
});
