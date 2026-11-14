import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { AdminDrivers } from "@/features/driver";

export const metadata: Metadata = { title: "Driver applications · GetDrove" };

/** /admin/drivers: approve or reject driver applications (#128). Admins only. */
export default function Page() {
  return (
    <RequireAuth>
      <AdminDrivers />
    </RequireAuth>
  );
}
