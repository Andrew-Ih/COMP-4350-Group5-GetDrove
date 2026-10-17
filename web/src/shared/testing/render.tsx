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

/**
 * Replaces fetch for one test, answering by path instead of in order: for screens that
 * make several calls at once. Keys are matched against the end of the URL's path; a
 * function gets the request URL. Unmatched calls get a 500.
 *
 *   const fetchSpy = mockApi({
 *     "/accounts/me": { status: 200, body: maya },
 *     "/trips/search": (url) => ({ status: 200, body: url.searchParams.has("lat") ? results : [] }),
 *   });
 */
export function mockApi(routes: Record<string, FakeResponse | ((url: URL) => FakeResponse)>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    const match = Object.entries(routes).find(([path]) => url.pathname.endsWith(path));
    const answer = match ? match[1] : { status: 500, body: problem(500, "unexpected_error", `No fake response for ${url.pathname}`) };
    const next = typeof answer === "function" ? answer(url) : answer;
    const hasBody = next.body !== undefined && next.status !== 204;
    return new Response(hasBody ? JSON.stringify(next.body) : null, {
      status: next.status,
      headers: { "Content-Type": next.status >= 400 ? "application/problem+json" : "application/json" },
    });
  });
}
