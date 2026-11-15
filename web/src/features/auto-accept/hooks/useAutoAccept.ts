"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAutoAcceptRules, saveAutoAcceptRules } from "../api/autoAcceptApi";
import type { AutoAcceptRules } from "../model/rules";

const RULES = ["trips", "auto-accept"] as const;

// Errors are an ApiError when the API answered, or a TypeError when the request never got
// there (offline, server down), so they're typed as Error and checked before use.

/** The driver's auto-accept rules. */
export function useAutoAcceptRules() {
  return useQuery<AutoAcceptRules, Error>({ queryKey: RULES, queryFn: getAutoAcceptRules });
}

/** Saves the rules; what the API saved becomes the rules shown. */
export function useSaveAutoAcceptRules() {
  const queryClient = useQueryClient();
  return useMutation<AutoAcceptRules, Error, AutoAcceptRules>({
    mutationFn: saveAutoAcceptRules,
    onSuccess: (saved) => queryClient.setQueryData(RULES, saved),
  });
}
