import { describe, expect, it } from "vitest";

import { ApiError, networkProblem } from "./problem";
import { retryServerErrors } from "./retry";

const apiError = (status: number, code: string) =>
  new ApiError({ type: "about:blank", title: code, status, detail: code, instance: "/x", code, requestId: "r" });

describe("retryServerErrors", () => {
  it("tries a server error again once", () => {
    expect(retryServerErrors(0, apiError(503, "routing_unavailable"))).toBe(true);
    expect(retryServerErrors(1, apiError(503, "routing_unavailable"))).toBe(false);
  });

  it("tries a request that didn't get through again once", () => {
    expect(retryServerErrors(0, new ApiError(networkProblem()))).toBe(true);
    expect(retryServerErrors(1, new ApiError(networkProblem()))).toBe(false);
  });

  it.each([
    [404, "trip_not_found"],
    [401, "unauthorized"],
    [422, "invalid_input"],
    [409, "trip_full"],
  ])("never tries a %i (%s) again", (status, code) => {
    expect(retryServerErrors(0, apiError(status, code))).toBe(false);
  });
});
