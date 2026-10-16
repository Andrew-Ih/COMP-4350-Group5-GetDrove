"use client";

import { useMutation } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { resendVerification, signup, verifyEmail } from "../api/authApi";
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
