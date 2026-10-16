import type { Metadata } from "next";

import { AuthShell, VerifyEmail } from "@/features/auth";

export const metadata: Metadata = { title: "Verify your email · GetDrove" };

/** The page the verification email links to: /verify?token=… */
export default async function VerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const { token } = await searchParams;
  return (
    <AuthShell>
      <VerifyEmail token={typeof token === "string" ? token : undefined} />
    </AuthShell>
  );
}
