"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getAutoAcceptRules, saveAutoAcceptRules } from "../api/autoAcceptApi";
import type { AutoAcceptRules } from "../model/rules";

const RULES = ["trips", "auto-accept"] as const;

/** The driver's auto-accept rules. */
export function useAutoAcceptRules() {
  return useQuery<AutoAcceptRules, ApiError>({ queryKey: RULES, queryFn: getAutoAcceptRules });
}

/** Saves the rules; what the API saved becomes the rules shown. */
export function useSaveAutoAcceptRules() {
  const queryClient = useQueryClient();
  return useMutation<AutoAcceptRules, ApiError, AutoAcceptRules>({
    mutationFn: saveAutoAcceptRules,
    onSuccess: (saved) => queryClient.setQueryData(RULES, saved),
  });
}
