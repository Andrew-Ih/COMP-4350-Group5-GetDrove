import { delay, http, HttpResponse } from "msw";

import type { components as Accounts } from "@/shared/api/generated/accounts";

/**
 * Mock API for staying logged in (#225): POST /auth/refresh and POST /auth/logout.
 *
 * The real refresh token is an HttpOnly cookie the mock can't set, so the mock remembers
 * "logged in" in sessionStorage instead: logging in sets it, logging out clears it, and
 * refresh works while it's set. A reload then keeps you logged in, as with the real API.
 * Tests run without sessionStorage and use `mockSessionState` instead.
 */
const KEY = "getdrove-mock-session";
let inMemory = false; // where tests (Node, no sessionStorage) keep it

function storage(): Storage | undefined {
  try {
    return typeof sessionStorage === "undefined" ? undefined : sessionStorage;
  } catch {
    return undefined;
  }
}

export const mockSessionState = {
  isLoggedIn(): boolean {
    return storage()?.getItem(KEY) === "1" || inMemory;
  },
  logIn(): void {
    storage()?.setItem(KEY, "1");
    inMemory = true;
  },
  logOut(): void {
    storage()?.removeItem(KEY);
    inMemory = false;
  },
};

export const MOCK_TOKEN: Accounts["schemas"]["TokenResponse"] = {
  accessToken: "mock-access-token",
  tokenType: "Bearer",
  expiresIn: 900,
};

export const sessionHandlers = [
  http.post("*/api/accounts/auth/refresh", async () => {
    await delay(); // realistic in the browser, none in tests
    if (!mockSessionState.isLoggedIn()) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "Session expired",
          status: 401,
          detail: "Log in again.",
          instance: "/api/accounts/auth/refresh",
          code: "invalid_refresh_token",
          requestId: "mock",
        },
        { status: 401, headers: { "Content-Type": "application/problem+json" } },
      );
    }
    return HttpResponse.json(MOCK_TOKEN);
  }),

  http.post("*/api/accounts/auth/logout", () => {
    mockSessionState.logOut();
    return new HttpResponse(null, { status: 204 });
  }),
];
