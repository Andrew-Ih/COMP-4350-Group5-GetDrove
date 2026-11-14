"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import {
  approveDriver,
  getAdminDrivers,
  getApplicantDocument,
  getDocument,
  getDriverProfile,
  rejectDriver,
  saveVehicle,
  uploadDocuments,
} from "../api/driverApi";
import type { AdminDriver, AdminDriverStatus, DocumentKind, DriverProfile, Vehicle } from "../model/driver";

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
 * Opens a file in a new tab. It's fetched with the login token (a plain link wouldn't send
 * it), and the tab is opened first, while it still counts as the click, so the browser
 * doesn't block it.
 */
async function openInNewTab(load: () => Promise<Blob>): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const url = URL.createObjectURL(await load());
    if (tab) tab.location.href = url;
    else window.location.href = url;
  } catch (error) {
    tab?.close();
    throw error;
  }
}

/** Opens one of the student's own uploaded documents. */
export function useOpenDocument() {
  return useMutation<void, ApiError, DocumentKind>({ mutationFn: (kind) => openInNewTab(() => getDocument(kind)) });
}

// ---------------------------------------------------------------- admin (#128)

const adminKey = (status: AdminDriverStatus) => ["accounts", "admin", "drivers", status] as const;

/** Driver applications with a status, for admins. */
export function useAdminDrivers(status: AdminDriverStatus, enabled: boolean) {
  return useQuery<AdminDriver[], ApiError>({ queryKey: adminKey(status), queryFn: () => getAdminDrivers(status), enabled });
}

/** Opens an applicant's document, for admins. */
export function useOpenApplicantDocument() {
  return useMutation<void, ApiError, { userId: string; kind: DocumentKind }>({
    mutationFn: ({ userId, kind }) => openInNewTab(() => getApplicantDocument(userId, kind)),
  });
}

type Decision = { userId: string; approve: true } | { userId: string; approve: false; reason: string };

/**
 * Approves or rejects an application. Afterwards (either way) every list is fetched again:
 * the decided application moves from Pending to Approved or Rejected, and one someone else
 * already decided shows its real status.
 */
export function useDecideDriver() {
  const queryClient = useQueryClient();
  return useMutation<AdminDriver, ApiError, Decision>({
    mutationFn: (decision) => (decision.approve ? approveDriver(decision.userId) : rejectDriver(decision.userId, decision.reason)),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["accounts", "admin", "drivers"] }),
  });
}
