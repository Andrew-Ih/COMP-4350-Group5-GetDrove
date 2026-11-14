import { accountsApi, unwrap } from "@/shared/api";

import type { AdminDriverStatus, DocumentKind, Vehicle } from "../model/driver";

/** GET /api/accounts/me/driver: where the student's application to drive stands. */
export function getDriverProfile() {
  return unwrap(accountsApi.GET("/me/driver"));
}

/** PUT /api/accounts/me/driver/documents: both files at once, as multipart form data. */
export function uploadDocuments(licence: File, insurance: File) {
  return unwrap(
    accountsApi.PUT("/me/driver/documents", {
      // The generated type says string (OpenAPI's way of describing a file); the files go
      // in a FormData, and the browser sets the multipart Content-Type itself.
      body: { licence: licence as unknown as string, insurance: insurance as unknown as string },
      bodySerializer: (body) => {
        const form = new FormData();
        form.append("licence", body.licence as unknown as Blob);
        form.append("insurance", body.insurance as unknown as Blob);
        return form;
      },
    }),
  );
}

/** PUT /api/accounts/me/driver/vehicle */
export function saveVehicle(vehicle: Vehicle) {
  return unwrap(accountsApi.PUT("/me/driver/vehicle", { body: vehicle }));
}

/** GET /api/accounts/me/driver/documents/{kind}: the file as uploaded. */
export function getDocument(kind: DocumentKind) {
  return unwrap(accountsApi.GET("/me/driver/documents/{kind}", { params: { path: { kind } }, parseAs: "blob" })) as Promise<Blob>;
}

// ---------------------------------------------------------------- admin (#128)

/** GET /api/accounts/admin/drivers?status=: applications with that status, oldest first. Admins only. */
export function getAdminDrivers(status: AdminDriverStatus) {
  return unwrap(accountsApi.GET("/admin/drivers", { params: { query: { status } } }));
}

/** GET /api/accounts/admin/drivers/{id}/documents/{kind}: an applicant's file as uploaded. */
export function getApplicantDocument(userId: string, kind: DocumentKind) {
  return unwrap(
    accountsApi.GET("/admin/drivers/{user_id}/documents/{kind}", { params: { path: { user_id: userId, kind } }, parseAs: "blob" }),
  ) as Promise<Blob>;
}

/** POST /api/accounts/admin/drivers/{id}/approve: they can post trips straight away. */
export function approveDriver(userId: string) {
  return unwrap(accountsApi.POST("/admin/drivers/{user_id}/approve", { params: { path: { user_id: userId } } }));
}

/** POST /api/accounts/admin/drivers/{id}/reject: the reason is shown to the driver. */
export function rejectDriver(userId: string, reason: string) {
  return unwrap(accountsApi.POST("/admin/drivers/{user_id}/reject", { params: { path: { user_id: userId } }, body: { reason } }));
}
