import { describe, expect, it } from "vitest";

import { isUofMEmail, signupSchema } from "./signup";

const valid = {
  firstName: "Ada",
  lastName: "Lovelace",
  email: "ada@myumanitoba.ca",
  password: "correct horse",
};

describe("isUofMEmail", () => {
  it.each(["ada@myumanitoba.ca", "Ada@MyUManitoba.CA", "  ada@myumanitoba.ca "])(
    "accepts %j",
    (email) => expect(isUofMEmail(email)).toBe(true),
  );

  it.each(["ada@gmail.com", "ada@umanitoba.ca", "ada@myumanitoba.ca.evil.com", "@myumanitoba.ca", "a@b@myumanitoba.ca", ""])(
    "rejects %j",
    (email) => expect(isUofMEmail(email)).toBe(false),
  );
});

describe("signupSchema", () => {
  it("accepts a complete form and trims names and email", () => {
    const result = signupSchema.parse({ ...valid, firstName: " Ada ", email: " ada@myumanitoba.ca " });
    expect(result.firstName).toBe("Ada");
    expect(result.email).toBe("ada@myumanitoba.ca");
  });

  it("needs a password of at least 10 characters, like the contract", () => {
    expect(signupSchema.safeParse({ ...valid, password: "123456789" }).success).toBe(false);
    expect(signupSchema.safeParse({ ...valid, password: "1234567890" }).success).toBe(true);
  });

  it("rejects passwords over 128 characters", () => {
    expect(signupSchema.safeParse({ ...valid, password: "x".repeat(129) }).success).toBe(false);
  });

  it("rejects a non-UofM email with a clear message", () => {
    const result = signupSchema.safeParse({ ...valid, email: "ada@gmail.com" });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe("Use your @myumanitoba.ca email.");
  });

  it("needs both names", () => {
    expect(signupSchema.safeParse({ ...valid, firstName: "  " }).success).toBe(false);
    expect(signupSchema.safeParse({ ...valid, lastName: "" }).success).toBe(false);
  });
});
