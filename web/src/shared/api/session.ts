/**
 * The access token from logging in, kept in memory only.
 *
 * Not in localStorage or a readable cookie, so a script injected into the page can't
 * steal a long-lived copy. It lasts 15 minutes and is lost on reload; the refresh token
 * (an HttpOnly cookie set by Accounts) is what gets a new one, once /auth/refresh is
 * built (#90).
 */
let accessToken: string | undefined;

export function setAccessToken(token: string | undefined): void {
  accessToken = token;
}

export function getAccessToken(): string | undefined {
  return accessToken;
}
