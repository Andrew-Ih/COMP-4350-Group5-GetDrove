import { accountsApi, unwrap } from "@/shared/api";

import type { LoginValues } from "../model/login";
import type { SignupValues } from "../model/signup";

/** POST /auth/signup: creates the account and sends the verification email. */
export function signup(values: SignupValues) {
  return unwrap(accountsApi.POST("/auth/signup", { body: values }));
}

/** POST /auth/verify: marks the email as verified. Fails with invalid_token or token_expired. */
export function verifyEmail(token: string) {
  return unwrap(accountsApi.POST("/auth/verify", { body: { token } }));
}

/** POST /auth/resend-verification: always succeeds, whether or not the account exists. */
export function resendVerification(email: string) {
  return unwrap(accountsApi.POST("/auth/resend-verification", { body: { email } }));
}

/** POST /auth/login: returns an access token and sets the refresh-token cookie. */
export function login(values: LoginValues) {
  return unwrap(accountsApi.POST("/auth/login", { body: values }));
}

/** GET /me: the logged-in student. Needs the access token. */
export function getMe() {
  return unwrap(accountsApi.GET("/me"));
}
