import type { Metadata } from "next";

import { AuthShell, SignupForm } from "@/features/auth";

export const metadata: Metadata = { title: "Sign up · GetDrove" };

export default function SignupPage() {
  return (
    <AuthShell>
      <SignupForm />
    </AuthShell>
  );
}
