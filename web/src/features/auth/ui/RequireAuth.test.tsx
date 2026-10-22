import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { endSession, setAccessToken } from "@/shared/api";
import { mockFetch, problem } from "@/shared/testing/render";

import { RequireAuth } from "./RequireAuth";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/ride",
}));

const EXPIRED = { status: 401, body: problem(401, "invalid_refresh_token", "Log in again.") };

afterEach(() => {
  endSession();
  replace.mockReset();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("RequireAuth", () => {
  it("keeps a student logged in after a reload, using the refresh cookie", async () => {
    const fetchSpy = mockFetch({ status: 200, body: { accessToken: "new", tokenType: "Bearer", expiresIn: 900 } });
    render(<RequireAuth>secret</RequireAuth>);

    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    expect(await screen.findByText("secret")).toBeInTheDocument();
    expect(String(fetchSpy.mock.calls[0]?.[0])).toContain("/accounts/auth/refresh");
    expect(replace).not.toHaveBeenCalled();
  });

  it("sends a logged-out visitor to log in, coming back here afterwards", async () => {
    mockFetch(EXPIRED);
    render(<RequireAuth>secret</RequireAuth>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fride"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("comes back with the same query, e.g. a search", async () => {
    mockFetch(EXPIRED);
    window.history.replaceState(null, "", "/ride?direction=to_campus&lat=49.87");
    render(<RequireAuth>secret</RequireAuth>);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith(`/login?next=${encodeURIComponent("/ride?direction=to_campus&lat=49.87")}`),
    );
  });

  it("shows the page straight away to a logged-in student", () => {
    const fetchSpy = mockFetch();
    setAccessToken("tok");
    render(<RequireAuth>secret</RequireAuth>);

    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("leaves the page when the student logs out (here or in another tab)", async () => {
    mockFetch(EXPIRED);
    setAccessToken("tok");
    render(<RequireAuth>secret</RequireAuth>);

    act(() => endSession());

    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fride"));
  });
});
