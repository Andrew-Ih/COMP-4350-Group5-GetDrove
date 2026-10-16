import { describe, expect, it } from "vitest";

import type { Problem } from "@/shared/api";

import { fieldErrorsFrom } from "./serverErrors";

const base: Problem = {
  type: "about:blank",
  title: "Invalid input",
  status: 422,
  detail: "Check the highlighted fields.",
  instance: "/api/accounts/auth/signup",
  code: "invalid_input",
};

describe("fieldErrorsFrom", () => {
  it("puts each error on its field, with or without a path in front", () => {
    const problem = {
      ...base,
      errors: [
        { field: "password", message: "Too short" },
        { field: "body.firstName", message: "Required" },
      ],
    };
    expect(fieldErrorsFrom(problem, ["password", "firstName"] as const)).toEqual({
      fields: { password: "Too short", firstName: "Required" },
    });
  });

  it("falls back to a form-level message when no field matches", () => {
    expect(fieldErrorsFrom(base, ["email"] as const)).toEqual({
      fields: {},
      form: "Check the highlighted fields.",
    });
  });
});
