"use client";

import { useQuery } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getMe } from "../api/authApi";

/** The logged-in student (GET /me), cached for the session. */
export function useCurrentUser() {
  return useQuery<Awaited<ReturnType<typeof getMe>>, ApiError>({
    queryKey: ["me"],
    queryFn: getMe,
    staleTime: 5 * 60_000,
  });
}
