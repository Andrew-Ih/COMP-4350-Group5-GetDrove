import type { Metadata } from "next";

import { AuthShell, LoginForm } from "@/features/auth";

export const metadata: Metadata = { title: "Log in · GetDrove" };

/** /login, or /login?next=/trips to come back to a page after logging in. */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  return (
    <AuthShell>
      <LoginForm next={typeof next === "string" ? next : undefined} />
    </AuthShell>
  );
}
