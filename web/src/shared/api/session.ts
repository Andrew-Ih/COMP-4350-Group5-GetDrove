import { apiBaseUrl } from "@/shared/config/env";

import type { components } from "./generated/accounts";

/**
 * The logged-in session (#225).
 *
 * The access token is kept in memory only: not in localStorage or a readable cookie, so a
 * script injected into the page can't steal a long-lived copy. It lasts 15 minutes and is
 * lost on reload. The refresh token is an HttpOnly cookie set by Accounts (JavaScript can't
 * read it) and is what gets a new access token: on page load, shortly before the current
 * one expires, and when an API call says it has expired.
 *
 * Every refresh swaps the cookie for a new one (#90), and Accounts treats an old cookie
 * coming back as stolen and ends every session. So only one refresh ever runs at a time:
 * callers in a tab share the same request, and tabs take turns with the browser's lock
 * (navigator.locks), each using the cookie the previous one left.
 */

type TokenResponse = components["schemas"]["TokenResponse"];

const REFRESH_LOCK = "getdrove-session-refresh";
/** Refresh this long before the access token expires. */
const REFRESH_EARLY_SECONDS = 60;
/** Other tabs hear about logging out on this channel. */
const CHANNEL = "getdrove-session";

let accessToken: string | undefined;
let refreshTimer: ReturnType<typeof setTimeout> | undefined;
let inFlight: Promise<boolean> | undefined;
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

/** For React's useSyncExternalStore: called whenever the student logs in or out. */
export function subscribeToSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAccessToken(): string | undefined {
  return accessToken;
}

/** Sets the token directly, with no refresh scheduled. For tests; the app uses startSession. */
export function setAccessToken(token: string | undefined): void {
  clearTimeout(refreshTimer);
  accessToken = token;
  notify();
}

/** After logging in or refreshing: keep the token, and refresh it before it expires. */
export function startSession(token: Pick<TokenResponse, "accessToken" | "expiresIn">): void {
  setAccessToken(token.accessToken);
  const delay = Math.max(0, token.expiresIn - REFRESH_EARLY_SECONDS) * 1000;
  refreshTimer = setTimeout(() => void refreshSession(), delay);
}

/** Forgets the session in this tab. */
export function endSession(): void {
  setAccessToken(undefined);
}

async function requestRefresh(): Promise<boolean> {
  try {
    // Same origin, so the browser sends the HttpOnly cookie (its path is /api/accounts/auth).
    const response = await globalThis.fetch(`${apiBaseUrl}/accounts/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
    });
    if (!response.ok) {
      endSession(); // 401 invalid_refresh_token: logged out, expired, or ended elsewhere
      return false;
    }
    startSession((await response.json()) as TokenResponse);
    return true;
  } catch {
    return false; // offline or the server is down: keep what we have, try again later
  }
}

/**
 * Gets a new access token with the refresh cookie. True if the student is logged in
 * afterwards. However many callers ask at once, only one request is sent, and never two
 * at once across tabs.
 */
export function refreshSession(): Promise<boolean> {
  if (!inFlight) {
    const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
    // The lock resolves with requestRefresh's own result (its types don't unwrap it).
    const refresh = locks
      ? (locks.request(REFRESH_LOCK, requestRefresh) as Promise<unknown> as Promise<boolean>)
      : requestRefresh();
    inFlight = refresh.finally(() => {
      inFlight = undefined;
    });
  }
  return inFlight;
}

function channel(): BroadcastChannel | undefined {
  return typeof BroadcastChannel === "undefined" ? undefined : new BroadcastChannel(CHANNEL);
}

/**
 * Logs out: the refresh cookie stops working (POST /auth/logout always succeeds), the
 * token is forgotten, and other open tabs are told to forget theirs too.
 */
export async function logOut(): Promise<void> {
  try {
    await globalThis.fetch(`${apiBaseUrl}/accounts/auth/logout`, { method: "POST", credentials: "same-origin" });
  } catch {
    // Offline: still forget the session here. The cookie expires by itself.
  } finally {
    endSession();
    const tabs = channel();
    tabs?.postMessage("logged-out");
    tabs?.close();
  }
}

// When another tab logs out, this one does too.
if (typeof window !== "undefined") {
  const tabs = channel();
  if (tabs) {
    tabs.onmessage = (event) => {
      if (event.data === "logged-out") endSession();
    };
    // Node (tests) only: don't keep the process alive just to listen. Browsers have no unref.
    (tabs as BroadcastChannel & { unref?: () => void }).unref?.();
  }
}
