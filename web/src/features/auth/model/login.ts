import { z } from "zod";

import { isUofMEmail } from "./signup";

/** The log in form. Like LoginRequest in the contract: a UofM email and any password. */
export const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your UofM email.")
    .max(254, "That email is too long.")
    .refine(isUofMEmail, { message: "Use your @myumanitoba.ca email." }),
  password: z.string().min(1, "Enter your password.").max(128, "That password is too long."),
});

export type LoginValues = z.infer<typeof loginSchema>;

/** Where to go after logging in when no page asked for it: the rider home. */
export const AFTER_LOGIN = "/ride";

/**
 * The page to return to after logging in, from ?next=. Only paths on this site are
 * allowed, so a link can't send someone to another site after they log in.
 */
export function safeNext(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return AFTER_LOGIN;
  }
  return next;
}
