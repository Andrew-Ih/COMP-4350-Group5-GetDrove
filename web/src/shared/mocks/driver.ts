import { http, HttpResponse } from "msw";

import type { components as Accounts } from "@/shared/api/generated/accounts";

/**
 * Mock API for applying to drive (#12, #126), matching the Accounts contract. The student
 * starts with no application, so Post a trip shows "Get approved to drive" first.
 *
 * Until the admin page (#128) is there to decide, the licence file's name decides:
 *   - a name with "approve" in it (e.g. approve.pdf) → approved straight away
 *   - a name with "reject" in it                      → rejected, with a reason
 *   - anything else                                   → pending
 * Files must be PDF, JPEG or PNG and up to 5 MB, as in the contract.
 */

type DriverProfile = Accounts["schemas"]["DriverProfile"];
type Vehicle = Accounts["schemas"]["Vehicle"];

const ACCEPTED = ["application/pdf", "image/jpeg", "image/png"];
const MAX_BYTES = 5 * 1024 * 1024;

function empty(): DriverProfile {
  return { status: "none", rejectionReason: null, documents: { licence: false, insurance: false }, vehicle: null, submittedAt: null, reviewedAt: null };
}

let profile = empty();
const files = new Map<string, File>();

/** Starts again with no application (for tests). */
export function resetDriverApplication() {
  profile = empty();
  files.clear();
}

function problem(status: number, code: string, detail: string, extra: object = {}) {
  return HttpResponse.json(
    { type: "about:blank", title: detail, status, detail, instance: "/api/accounts/me/driver", code, requestId: "mock", ...extra },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

export const driverHandlers = [
  http.get("*/api/accounts/me/driver", () => HttpResponse.json(profile)),

  http.put("*/api/accounts/me/driver/documents", async ({ request }) => {
    if (profile.status === "approved") return problem(409, "driver_already_approved", "You're already approved");
    const form = await request.formData();
    const licence = form.get("licence");
    const insurance = form.get("insurance");
    if (!(licence instanceof File) || !(insurance instanceof File)) {
      return problem(422, "invalid_input", "Invalid input", { errors: [{ field: "licence", message: "Both files are required" }] });
    }
    for (const file of [licence, insurance]) {
      if (!ACCEPTED.includes(file.type)) return problem(422, "unsupported_file_type", "Use a PDF, JPEG or PNG file");
      if (file.size > MAX_BYTES) return problem(422, "file_too_large", "Files must be 5 MB or smaller");
    }
    files.set("licence", licence);
    files.set("insurance", insurance);
    const now = new Date().toISOString();
    const name = licence.name.toLowerCase();
    profile = {
      ...profile,
      documents: { licence: true, insurance: true },
      submittedAt: now,
      status: name.includes("approve") ? "approved" : name.includes("reject") ? "rejected" : "pending",
      rejectionReason: name.includes("reject") ? "The licence photo is too blurry to read. Upload a clearer one." : null,
      reviewedAt: name.includes("approve") || name.includes("reject") ? now : null,
    };
    return HttpResponse.json(profile);
  }),

  http.get("*/api/accounts/me/driver/documents/:kind", ({ params }) => {
    const file = files.get(String(params.kind));
    if (!file) return problem(404, "document_not_found", "No document of this kind uploaded");
    return new HttpResponse(file, { headers: { "Content-Type": file.type } });
  }),

  http.put("*/api/accounts/me/driver/vehicle", async ({ request }) => {
    const body = (await request.json()) as Vehicle;
    const errors: { field: string; message: string }[] = (["make", "model", "colour"] as const)
      .filter((f) => !body[f] || body[f].length > 30)
      .map((field) => ({ field, message: "Use 1 to 30 characters" }));
    if (!/^[A-Za-z0-9]{2,8}$/.test(body.plate ?? "")) errors.push({ field: "plate", message: "Use 2 to 8 letters and numbers" });
    if (errors.length) return problem(422, "invalid_input", "Invalid input", { errors });
    profile = { ...profile, vehicle: { ...body, plate: body.plate.toUpperCase() } };
    return HttpResponse.json(profile);
  }),
];
