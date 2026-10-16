import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { RideHome } from "@/features/ride";

export const metadata: Metadata = { title: "Find a ride · GetDrove" };

export default function RidePage() {
  return (
    <RequireAuth>
      <RideHome />
    </RequireAuth>
  );
}
