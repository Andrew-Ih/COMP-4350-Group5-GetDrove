import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { PostTrip } from "@/features/drive";
import { DriverGate } from "@/features/driver";

export const metadata: Metadata = { title: "Post a trip · GetDrove" };

export default function PostTripPage() {
  return (
    <RequireAuth>
      <DriverGate>
        <PostTrip />
      </DriverGate>
    </RequireAuth>
  );
}
