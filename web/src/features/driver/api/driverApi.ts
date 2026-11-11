import { accountsApi, unwrap } from "@/shared/api";

import type { DocumentKind, Vehicle } from "../model/driver";

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
