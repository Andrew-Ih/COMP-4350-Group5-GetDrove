import { http, HttpResponse } from "msw";

import type { components as Accounts } from "@/shared/api/generated/accounts";

import { maya } from "./data";
import { mockSessionState } from "./session";

/**
 * Mock API for applying to drive (#12, #126), matching the Accounts contract. The student
 * starts with no application, so Post a trip shows "Get approved to drive" first.
 *
 * The licence file's name can decide straight away, to try each state quickly:
 *   - a name with "approve" in it (e.g. approve.pdf) → approved straight away
 *   - a name with "reject" in it                      → rejected, with a reason
 *   - anything else                                   → pending, for an admin to decide
 * Files must be PDF, JPEG or PNG and up to 5 MB, as in the contract.
 *
 * Admins (#128): log in as admin@myumanitoba.ca and open /admin/drivers. The list has a few
 * sample applicants, plus the student's own application once it's submitted, so a decision
 * there shows up on their driver page. Everyone else gets 403 forbidden.
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

type AdminDriver = Accounts["schemas"]["AdminDriver"];

const daysAgo = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString();

/** Other students' applications, for the admin page. */
function sampleApplicants(): AdminDriver[] {
  const applicant = (
    userId: string,
    firstName: string,
    lastName: string,
    vehicle: Vehicle | null,
    submittedDaysAgo: number,
    decided?: { status: "approved" | "rejected"; reason?: string },
  ): AdminDriver => ({
    userId,
    firstName,
    lastName,
    email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}@myumanitoba.ca`,
    status: decided?.status ?? "pending",
    vehicle,
    documents: { licence: true, insurance: true },
    submittedAt: daysAgo(submittedDaysAgo),
    reviewedAt: decided ? daysAgo(submittedDaysAgo - 1) : null,
    rejectionReason: decided?.reason ?? null,
  });
  return [
    applicant("aaaaaaaa-0000-4000-8000-000000000001", "Priya", "Patel", { make: "Honda", model: "Civic", colour: "Grey", plate: "GDR123" }, 3),
    applicant("aaaaaaaa-0000-4000-8000-000000000002", "Daniel", "Okafor", null, 2),
    applicant("aaaaaaaa-0000-4000-8000-000000000003", "Jordan", "Lee", { make: "Kia", model: "Soul", colour: "Blue", plate: "KIA42" }, 1),
    applicant("aaaaaaaa-0000-4000-8000-000000000004", "Amira", "Haddad", { make: "Toyota", model: "Corolla", colour: "White", plate: "AMR7" }, 9, { status: "approved" }),
    applicant("aaaaaaaa-0000-4000-8000-000000000005", "Sam", "Novak", { make: "Ford", model: "Focus", colour: "Red", plate: "SAM55" }, 6, {
      status: "rejected",
      reason: "The insurance document has expired.",
    }),
  ];
}

let applicants = sampleApplicants();

/** Starts again with no application, and the sample applicants undecided (for tests). */
export function resetDriverApplication() {
  profile = empty();
  files.clear();
  applicants = sampleApplicants();
}

/** The student's own application as an admin sees it, once it's been submitted. */
function ownApplication(): AdminDriver | undefined {
  if (profile.status === "none") return undefined;
  return { userId: maya.id, firstName: maya.firstName, lastName: maya.lastName, email: maya.email, ...profile, status: profile.status };
}

function allApplications(): AdminDriver[] {
  const own = ownApplication();
  return own ? [...applicants, own] : applicants;
}

/** Saves an admin's decision, on the student's own application or a sample one. */
function decide(userId: string, changes: Pick<AdminDriver, "status" | "rejectionReason">): AdminDriver {
  const reviewedAt = new Date().toISOString();
  if (userId === maya.id) {
    profile = { ...profile, ...changes, reviewedAt };
    return ownApplication()!;
  }
  applicants = applicants.map((a) => (a.userId === userId ? { ...a, ...changes, reviewedAt } : a));
  return applicants.find((a) => a.userId === userId)!;
}

/** A one-page PDF saying what it stands in for: the sample applicants' "documents". */
function samplePdf(title: string): Blob {
  const text = `BT /F1 24 Tf 72 720 Td (${title}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets = objects.map((object, i) => {
    const offset = body.length;
    body += `${i + 1} 0 obj\n${object}\nendobj\n`;
    return offset;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([body], { type: "application/pdf" });
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

  // ---------------------------------------------------------------- admin (#128)

  http.get("*/api/accounts/admin/drivers", ({ request }) => {
    if (!mockSessionState.isAdmin()) return problem(403, "forbidden", "Only admins can do this");
    const status = new URL(request.url).searchParams.get("status") ?? "pending";
    if (!["pending", "approved", "rejected"].includes(status)) {
      return problem(422, "invalid_input", "Invalid input", { errors: [{ field: "status", message: "Use pending, approved or rejected" }] });
    }
    const list = allApplications()
      .filter((a) => a.status === status)
      .sort((a, b) => Date.parse(a.submittedAt ?? "") - Date.parse(b.submittedAt ?? "")); // oldest first
    return HttpResponse.json(list);
  }),

  http.get("*/api/accounts/admin/drivers/:userId/documents/:kind", ({ params }) => {
    if (!mockSessionState.isAdmin()) return problem(403, "forbidden", "Only admins can do this");
    const userId = String(params.userId);
    const kind = String(params.kind);
    if (userId === maya.id) {
      const file = files.get(kind);
      return file ? new HttpResponse(file, { headers: { "Content-Type": file.type } }) : problem(404, "document_not_found", "No document of this kind uploaded");
    }
    const applicant = applicants.find((a) => a.userId === userId);
    if (!applicant) return problem(404, "document_not_found", "No document of this kind uploaded");
    const label = kind === "licence" ? "Driver's licence" : "Proof of insurance";
    return new HttpResponse(samplePdf(`${label}: ${applicant.firstName} ${applicant.lastName}`), { headers: { "Content-Type": "application/pdf" } });
  }),

  http.post("*/api/accounts/admin/drivers/:userId/approve", ({ params }) => {
    if (!mockSessionState.isAdmin()) return problem(403, "forbidden", "Only admins can do this");
    const found = allApplications().find((a) => a.userId === String(params.userId));
    if (!found) return problem(404, "driver_not_found", "No driver application for this user");
    if (found.status !== "pending") return problem(409, "driver_not_pending", "This application isn't pending");
    if (!found.vehicle || !found.documents.licence || !found.documents.insurance) {
      return problem(409, "vehicle_missing", "The driver hasn't saved a vehicle yet");
    }
    return HttpResponse.json(decide(found.userId, { status: "approved", rejectionReason: null }));
  }),

  http.post("*/api/accounts/admin/drivers/:userId/reject", async ({ params, request }) => {
    if (!mockSessionState.isAdmin()) return problem(403, "forbidden", "Only admins can do this");
    const { reason } = (await request.json()) as Accounts["schemas"]["RejectDriverRequest"];
    if (!reason || reason.length > 500) {
      return problem(422, "invalid_input", "Invalid input", { errors: [{ field: "reason", message: "Use 1 to 500 characters" }] });
    }
    const found = allApplications().find((a) => a.userId === String(params.userId));
    if (!found) return problem(404, "driver_not_found", "No driver application for this user");
    if (found.status !== "pending") return problem(409, "driver_not_pending", "This application isn't pending");
    return HttpResponse.json(decide(found.userId, { status: "rejected", rejectionReason: reason }));
  }),
];
