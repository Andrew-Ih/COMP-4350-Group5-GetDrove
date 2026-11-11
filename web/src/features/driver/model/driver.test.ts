import { describe, expect, it } from "vitest";

import { buildVehicle, type DriverProfile, fileProblem, serverFieldErrors, statusMessage, uploadError } from "./driver";

const file = (type: string, bytes = 1000) => new File([new Uint8Array(bytes)], "doc", { type });

const profile = (changes: Partial<DriverProfile> = {}): DriverProfile => ({
  status: "none",
  rejectionReason: null,
  documents: { licence: false, insurance: false },
  vehicle: null,
  submittedAt: null,
  reviewedAt: null,
  ...changes,
});

describe("fileProblem", () => {
  it("accepts PDF, JPEG and PNG up to 5 MB", () => {
    expect(fileProblem(file("application/pdf"))).toBeUndefined();
    expect(fileProblem(file("image/jpeg"))).toBeUndefined();
    expect(fileProblem(file("image/png", 5 * 1024 * 1024))).toBeUndefined();
  });

  it("refuses other types and bigger files", () => {
    expect(fileProblem(file("image/gif"))).toBe("Use a PDF, JPEG or PNG file.");
    expect(fileProblem(file("application/pdf", 5 * 1024 * 1024 + 1))).toMatch(/over 5 MB/);
  });
});

describe("statusMessage", () => {
  it("explains each status, with the reason when rejected", () => {
    expect(statusMessage(profile()).title).toBe("Become a driver");
    expect(statusMessage(profile({ status: "pending" })).title).toBe("We're checking your documents");
    expect(statusMessage(profile({ status: "approved" })).title).toBe("You're approved to drive");
    expect(statusMessage(profile({ status: "rejected", rejectionReason: "Insurance has expired." }))).toEqual({
      title: "Your application wasn't approved",
      text: "Insurance has expired.",
    });
  });
});

describe("buildVehicle", () => {
  it("trims the fields and saves the plate in uppercase without spaces", () => {
    expect(buildVehicle({ make: " Honda ", model: "Civic", colour: "Grey", plate: "abc 123" })).toEqual({
      vehicle: { make: "Honda", model: "Civic", colour: "Grey", plate: "ABC123" },
    });
  });

  it("checks the same rules as the backend", () => {
    const result = buildVehicle({ make: "", model: "x".repeat(31), colour: "Grey", plate: "A" });
    expect(result).toEqual({
      errors: { make: "Enter the make.", model: "Use 30 characters or fewer.", plate: "Use 2 to 8 letters and numbers, e.g. ABC123." },
    });
    expect("errors" in buildVehicle({ make: "Kia", model: "Soul", colour: "Blue", plate: "ABC-123" })).toBe(true);
    expect("errors" in buildVehicle({ make: "Kia", model: "Soul", colour: "Blue", plate: "ABCDEFGHI" })).toBe(true);
  });
});

describe("server errors", () => {
  it("puts field errors on the fields they belong to", () => {
    expect(serverFieldErrors([{ field: "body.plate", message: "Too long" }, { field: "other", message: "x" }])).toEqual({ plate: "Too long" });
    expect(serverFieldErrors(null)).toEqual({});
  });

  it("explains upload errors", () => {
    expect(uploadError("file_too_large")).toMatch(/over 5 MB/);
    expect(uploadError("unsupported_file_type")).toMatch(/PDF, JPEG or PNG/);
    expect(uploadError("driver_already_approved")).toMatch(/already approved/);
    expect(uploadError(undefined)).toMatch(/Try again/);
  });
});
