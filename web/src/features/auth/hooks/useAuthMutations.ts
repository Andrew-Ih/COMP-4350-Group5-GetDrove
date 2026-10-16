"use client";

import { useMutation } from "@tanstack/react-query";

import { type ApiError, setAccessToken } from "@/shared/api";

import { login, resendVerification, signup, verifyEmail } from "../api/authApi";
import type { LoginValues } from "../model/login";
import type { SignupValues } from "../model/signup";

export function useSignup() {
  return useMutation<Awaited<ReturnType<typeof signup>>, ApiError, SignupValues>({ mutationFn: signup });
}

export function useVerifyEmail() {
  return useMutation<unknown, ApiError, string>({ mutationFn: verifyEmail });
}

export function useResendVerification() {
  return useMutation<unknown, ApiError, string>({ mutationFn: resendVerification });
}

/** Logs in and keeps the access token in memory for every later API call. */
export function useLogin() {
  return useMutation<Awaited<ReturnType<typeof login>>, ApiError, LoginValues>({
    mutationFn: login,
    onSuccess: (token) => setAccessToken(token.accessToken),
  });
}
