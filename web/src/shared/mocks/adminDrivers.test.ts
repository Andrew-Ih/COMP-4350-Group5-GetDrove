// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as AccountsPaths } from "@/shared/api/generated/accounts";
import { ApiError, unwrap } from "@/shared/api/problem";

import { resetDriverApplication } from "./driver";
import { server } from "./server";
import { mockSessionState } from "./session";

const fetch = (request: Request) => globalThis.fetch(request);
const accounts = createClient<AccountsPaths>({ baseUrl: "http://localhost/api/accounts", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetDriverApplication();
  mockSessionState.logOut();
});
afterAll(() => server.close());

const list = (status: "pending" | "approved" | "rejected" = "pending") =>
  unwrap(accounts.GET("/admin/drivers", { params: { query: { status } } }));
const approve = (userId: string) => unwrap(accounts.POST("/admin/drivers/{user_id}/approve", { params: { path: { user_id: userId } } }));
const reject = (userId: string, reason: string) =>
  unwrap(accounts.POST("/admin/drivers/{user_id}/reject", { params: { path: { user_id: userId } }, body: { reason } }));
const code = (promise: Promise<unknown>) => promise.then(() => undefined, (e: unknown) => (e as ApiError).code);

describe("mock API: admin driver approvals (#128)", () => {
  it("refuses students who aren't admins", async () => {
    mockSessionState.logIn();
    expect(await code(list())).toBe("forbidden");
  });

  it("logs in admin@myumanitoba.ca as the admin", async () => {
    await unwrap(accounts.POST("/auth/login", { body: { email: "admin@myumanitoba.ca", password: "long-enough-1" } }));
    const me = await unwrap(accounts.GET("/me"));
    expect(me.roles).toContain("admin");
  });

  it("lists pending applications oldest first, and moves them when decided", async () => {
    mockSessionState.logIn(true);
    const pending = await list();
    expect(pending.length).toBeGreaterThan(1);
    const times = pending.map((a) => Date.parse(a.submittedAt!));
    expect([...times].sort((a, b) => a - b)).toEqual(times);

    const withVehicle = pending.find((a) => a.vehicle)!;
    expect((await approve(withVehicle.userId)).status).toBe("approved");
    expect((await list("approved")).map((a) => a.userId)).toContain(withVehicle.userId);
    expect(await code(approve(withVehicle.userId))).toBe("driver_not_pending");

    const other = (await list()).find((a) => a.vehicle)!;
    expect((await reject(other.userId, "Expired insurance.")).rejectionReason).toBe("Expired insurance.");
  });

  it("won't approve an applicant without a vehicle, or reject without a reason", async () => {
    mockSessionState.logIn(true);
    const noVehicle = (await list()).find((a) => !a.vehicle)!;
    expect(await code(approve(noVehicle.userId))).toBe("vehicle_missing");
    expect(await code(reject(noVehicle.userId, ""))).toBe("invalid_input");
  });

  it("serves the sample applicants' documents as PDFs", async () => {
    mockSessionState.logIn(true);
    const [first] = await list();
    const { response } = await accounts.GET("/admin/drivers/{user_id}/documents/{kind}", {
      params: { path: { user_id: first!.userId, kind: "licence" } },
      parseAs: "blob",
    });
    expect(response.headers.get("Content-Type")).toBe("application/pdf");
  });
});
