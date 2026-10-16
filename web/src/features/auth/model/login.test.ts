import { describe, expect, it } from "vitest";

import { AFTER_LOGIN, loginSchema, safeNext } from "./login";

describe("loginSchema", () => {
  it("accepts a UofM email and any non-empty password", () => {
    expect(loginSchema.safeParse({ email: "ada@myumanitoba.ca", password: "x" }).success).toBe(true);
  });

  it("rejects a missing password or a non-UofM email", () => {
    expect(loginSchema.safeParse({ email: "ada@myumanitoba.ca", password: "" }).success).toBe(false);
    expect(loginSchema.safeParse({ email: "ada@gmail.com", password: "x" }).success).toBe(false);
  });
});

describe("safeNext", () => {
  it.each(["/ride", "/drive/new?x=1", "/trips"])("keeps the path %j", (path) => {
    expect(safeNext(path)).toBe(path);
  });

  it.each([undefined, "", "https://evil.example", "//evil.example", "/\\evil.example", "ride"])(
    "falls back for %j",
    (next) => expect(safeNext(next)).toBe(AFTER_LOGIN),
  );
});
