import { z } from "zod";

/** Only UofM student emails can sign up (contracts/openapi/accounts.json). */
export const UOFM_DOMAIN = "myumanitoba.ca";

/** Same rule as the Accounts service: ends in @myumanitoba.ca, ignoring case and spaces. */
export function isUofMEmail(value: string): boolean {
  const [local, domain, ...rest] = value.trim().toLowerCase().split("@");
  return rest.length === 0 && Boolean(local) && domain === UOFM_DOMAIN;
}

const uofmEmail = z
  .string()
  .trim()
  .min(1, "Enter your UofM email.")
  .max(254, "That email is too long.")
  .refine(isUofMEmail, { message: "Use your @myumanitoba.ca email." });

/** The sign-up form. Limits match SignupRequest in the Accounts contract. */
export const signupSchema = z.object({
  firstName: z.string().trim().min(1, "Enter your first name.").max(50, "Use 50 characters or fewer."),
  lastName: z.string().trim().min(1, "Enter your last name.").max(50, "Use 50 characters or fewer."),
  email: uofmEmail,
  password: z
    .string()
    .min(10, "Use at least 10 characters.")
    .max(128, "Use 128 characters or fewer."),
});

export type SignupValues = z.infer<typeof signupSchema>;

/** The "send a new link" form on the verify page. */
export const resendSchema = z.object({ email: uofmEmail });

export type ResendValues = z.infer<typeof resendSchema>;
