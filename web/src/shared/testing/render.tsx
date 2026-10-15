import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

/** Renders a component with the app's providers (a fresh TanStack Query client per test). */
export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

type FakeResponse = { status: number; body?: unknown };

/**
 * Replaces fetch for one test. Each API call gets the next response in the list; the
 * returned spy records the requests (e.g. to check what was sent).
 *
 *   const fetchSpy = mockFetch({ status: 201, body: { id: "1", email: "ada@myumanitoba.ca" } });
 */
export function mockFetch(...responses: FakeResponse[]) {
  const queue = [...responses];
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
    const next = queue.shift() ?? { status: 500, body: { detail: "No more fake responses" } };
    const hasBody = next.body !== undefined && next.status !== 204;
    return new Response(hasBody ? JSON.stringify(next.body) : null, {
      status: next.status,
      headers: { "Content-Type": next.status >= 400 ? "application/problem+json" : "application/json" },
    });
  });
}

/** A Problem Details body as the services return it. */
export function problem(status: number, code: string, detail: string, extra: object = {}) {
  return { type: "about:blank", title: detail, status, detail, instance: "/test", code, ...extra };
}
