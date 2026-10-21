import { CalendarDays } from "lucide-react";
import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { ComingSoon } from "@/features/coming-soon";

export const metadata: Metadata = { title: "My trips · GetDrove" };

/** /trips: a placeholder until the My trips screen lands (#131, Sprint 2). */
export default function MyTripsPage() {
  return (
    <RequireAuth>
      <ComingSoon
        title="My trips"
        description="Your upcoming and past trips, as a driver and as a rider, will show up here."
        icon={<CalendarDays className="size-7" />}
        sprint={2}
      />
    </RequireAuth>
  );
}
