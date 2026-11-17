import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { DriverPage } from "@/features/driver";

export const metadata: Metadata = { title: "Driving with GetDrove · GetDrove" };

/** /account/driver: apply to drive and see where the application stands (#12, #126). */
export default function Page() {
  return (
    <RequireAuth>
      <DriverPage />
    </RequireAuth>
  );
}
