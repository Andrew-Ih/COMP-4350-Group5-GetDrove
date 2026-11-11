import type { components } from "@/shared/api/generated/accounts";

export type DriverProfile = components["schemas"]["DriverProfile"];
export type DriverStatus = components["schemas"]["DriverStatus"];
export type Vehicle = components["schemas"]["Vehicle"];
export type DocumentKind = components["schemas"]["DocumentKind"];

/** The driver page. Notifications about approval link here too. */
export const DRIVER_HREF = "/account/driver";

/** The contract's limits for documents: PDF, JPEG or PNG, up to 5 MB each. */
export const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"] as const;
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export const DOCUMENT_LABEL: Record<DocumentKind, string> = { licence: "Driver's licence", insurance: "Proof of insurance" };

/** What's wrong with a file before it's sent, or undefined if it's fine. */
export function fileProblem(file: File): string | undefined {
  if (!(ACCEPTED_TYPES as readonly string[]).includes(file.type)) return "Use a PDF, JPEG or PNG file.";
  if (file.size > MAX_FILE_BYTES) return "This file is over 5 MB. Use a smaller scan or photo.";
  return undefined;
}

/** What each status means for the student. */
export function statusMessage(profile: DriverProfile): { title: string; text: string } {
  switch (profile.status) {
    case "none":
      return { title: "Become a driver", text: "Upload your driver's licence and proof of insurance, and add your vehicle. An admin checks them before you can post trips." };
    case "pending":
      return { title: "We're checking your documents", text: "An admin is reviewing your application. We'll let you know when it's done." };
    case "approved":
      return { title: "You're approved to drive", text: "You can post trips now." };
    case "rejected":
      return { title: "Your application wasn't approved", text: profile.rejectionReason ?? "Upload new documents to apply again." };
  }
}

export type VehicleForm = { make: string; model: string; colour: string; plate: string };
export type VehicleField = keyof VehicleForm;

/**
 * The vehicle to send, with the same rules as the backend: make, model and colour 1 to 30
 * characters; the plate 2 to 8 letters and digits (spaces removed, saved in uppercase).
 */
export function buildVehicle(form: VehicleForm): { vehicle: Vehicle } | { errors: Partial<Record<VehicleField, string>> } {
  const errors: Partial<Record<VehicleField, string>> = {};
  const text = (field: "make" | "model" | "colour", name: string) => {
    const value = form[field].trim();
    if (!value) errors[field] = `Enter the ${name}.`;
    else if (value.length > 30) errors[field] = `Use 30 characters or fewer.`;
    return value;
  };
  const make = text("make", "make");
  const model = text("model", "model");
  const colour = text("colour", "colour");
  const plate = form.plate.replace(/\s+/g, "").toUpperCase();
  if (!/^[A-Z0-9]{2,8}$/.test(plate)) errors.plate = "Use 2 to 8 letters and numbers, e.g. ABC123.";
  return Object.keys(errors).length > 0 ? { errors } : { vehicle: { make, model, colour, plate } };
}

/** The server's field errors (422 `errors`), by field, for the fields this form has. */
export function serverFieldErrors(errors: { field: string; message: string }[] | null | undefined): Partial<Record<VehicleField, string>> {
  const result: Partial<Record<VehicleField, string>> = {};
  for (const e of errors ?? []) {
    const field = e.field.split(".").at(-1) as VehicleField;
    if (["make", "model", "colour", "plate"].includes(field)) result[field] = e.message;
  }
  return result;
}

/** What the student is told when uploading fails, by the API's error code. */
export function uploadError(code: string | undefined): string {
  switch (code) {
    case "unsupported_file_type":
      return "One of the files isn't a PDF, JPEG or PNG.";
    case "file_too_large":
      return "One of the files is over 5 MB.";
    case "driver_already_approved":
      return "You're already approved, so there's nothing to upload.";
    default:
      return "We couldn't upload your documents. Try again.";
  }
}
