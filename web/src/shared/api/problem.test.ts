import { describe, expect, it } from "vitest";

import { ApiError, toProblem, unwrap } from "./problem";

const conflict = {
  type: "about:blank",
  title: "Conflict",
  status: 409,
  detail: "An account with this email already exists",
  instance: "/api/accounts/auth/signup",
  code: "email_taken",
  requestId: "abc123",
};

describe("toProblem", () => {
  it("keeps a Problem Details body as it is", () => {
    const response = new Response(null, { status: 409 });
    expect(toProblem(response, conflict)).toEqual(conflict);
  });

  it("turns a gateway error page into service_unavailable", () => {
    const response = new Response("Bad Gateway", { status: 502, statusText: "Bad Gateway" });
    const problem = toProblem(response, "Bad Gateway");
    expect(problem.status).toBe(502);
    expect(problem.code).toBe("service_unavailable");
  });

  it("turns any other non-problem body into unexpected_error", () => {
    const response = new Response(null, { status: 500 });
    expect(toProblem(response, undefined).code).toBe("unexpected_error");
  });
});

describe("unwrap", () => {
  it("returns the data of a successful call", async () => {
    const call = Promise.resolve({ data: { id: 1 }, response: new Response(null, { status: 200 }) });
    await expect(unwrap(call)).resolves.toEqual({ id: 1 });
  });

  it("throws an ApiError with the problem's code", async () => {
    const call = Promise.resolve({ error: conflict, response: new Response(null, { status: 409 }) });
    const error = await unwrap(call).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("email_taken");
    expect((error as ApiError).status).toBe(409);
  });
});
