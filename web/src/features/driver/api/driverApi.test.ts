// @vitest-environment node

import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { ApiError } from "@/shared/api";
import { resetDriverApplication } from "@/shared/mocks/driver";
import { server } from "@/shared/mocks/server";

import { getDocument, getDriverProfile, saveVehicle, uploadDocuments } from "./driverApi";

// Absolute URLs: Node has no page origin to resolve "/api/..." against.
vi.mock("@/shared/config/env", () => ({ apiBaseUrl: "http://localhost/api", stripePublishableKey: "", apiMocking: false }));

// These API functions against the mock API, so the multipart upload is checked end to end.
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetDriverApplication();
});
afterAll(() => server.close());

const pdf = (name: string, bytes = 10) => new File([new Uint8Array(bytes)], name, { type: "application/pdf" });
const failure = (call: Promise<unknown>) => call.then(() => undefined).catch((e: unknown) => (e as ApiError).code);

describe("driver API (against the mock API)", () => {
  it("starts with no application", async () => {
    expect((await getDriverProfile()).status).toBe("none");
  });

  it("sends both files as multipart form data, and the application becomes pending", async () => {
    const profile = await uploadDocuments(pdf("licence.pdf"), pdf("insurance.pdf"));
    expect(profile).toMatchObject({ status: "pending", documents: { licence: true, insurance: true } });
    expect((await getDocument("licence")).size).toBe(10);
  });

  it("is approved or rejected by the licence file's name in the mock, and refuses uploads once approved", async () => {
    expect((await uploadDocuments(pdf("reject.pdf"), pdf("insurance.pdf"))).rejectionReason).toBeTruthy();
    expect((await uploadDocuments(pdf("approve.pdf"), pdf("insurance.pdf"))).status).toBe("approved");
    expect(await failure(uploadDocuments(pdf("licence.pdf"), pdf("insurance.pdf")))).toBe("driver_already_approved");
  });

  it("is refused for other file types and files over 5 MB", async () => {
    const gif = new File(["gif"], "licence.gif", { type: "image/gif" });
    expect(await failure(uploadDocuments(gif, pdf("insurance.pdf")))).toBe("unsupported_file_type");
    expect(await failure(uploadDocuments(pdf("licence.pdf", 6 * 1024 * 1024), pdf("insurance.pdf")))).toBe("file_too_large");
  });

  it("saves a vehicle with the plate in uppercase, and checks the fields", async () => {
    expect((await saveVehicle({ make: "Honda", model: "Civic", colour: "Grey", plate: "abc123" })).vehicle?.plate).toBe("ABC123");
    expect(await failure(saveVehicle({ make: "", model: "Civic", colour: "Grey", plate: "A" }))).toBe("invalid_input");
  });
});
