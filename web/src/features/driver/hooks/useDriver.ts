"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getDocument, getDriverProfile, saveVehicle, uploadDocuments } from "../api/driverApi";
import type { DocumentKind, DriverProfile, Vehicle } from "../model/driver";

const KEY = ["accounts", "me", "driver"] as const;

/** Where the student's application to drive stands. */
export function useDriverProfile() {
  return useQuery<DriverProfile, ApiError>({ queryKey: KEY, queryFn: getDriverProfile });
}

export function useUploadDocuments() {
  const queryClient = useQueryClient();
  return useMutation<DriverProfile, ApiError, { licence: File; insurance: File }>({
    mutationFn: ({ licence, insurance }) => uploadDocuments(licence, insurance),
    onSuccess: (profile) => queryClient.setQueryData(KEY, profile),
  });
}

export function useSaveVehicle() {
  const queryClient = useQueryClient();
  return useMutation<DriverProfile, ApiError, Vehicle>({
    mutationFn: saveVehicle,
    onSuccess: (profile) => queryClient.setQueryData(KEY, profile),
  });
}

/**
 * Opens an uploaded document in a new tab. It's fetched with the login token (a plain link
 * wouldn't send it), and the tab is opened first, while it still counts as the click, so
 * the browser doesn't block it.
 */
export function useOpenDocument() {
  return useMutation<void, ApiError, DocumentKind>({
    mutationFn: async (kind) => {
      const tab = window.open("", "_blank");
      try {
        const blob = await getDocument(kind);
        const url = URL.createObjectURL(blob);
        if (tab) tab.location.href = url;
        else window.location.href = url;
      } catch (error) {
        tab?.close();
        throw error;
      }
    },
  });
}
