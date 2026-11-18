import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { AutoAcceptSettings } from "@/features/auto-accept";

export const metadata: Metadata = { title: "Auto-accept · GetDrove" };

/** /account/auto-accept: the driver's auto-accept rules (#45). */
export default function Page() {
  return (
    <RequireAuth>
      <AutoAcceptSettings />
    </RequireAuth>
  );
}
