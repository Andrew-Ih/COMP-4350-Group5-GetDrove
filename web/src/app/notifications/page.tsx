import { Bell } from "lucide-react";
import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { ComingSoon } from "@/features/coming-soon";

export const metadata: Metadata = { title: "Notifications · GetDrove" };

/** /notifications: a placeholder until notifications land in Sprint 2. */
export default function NotificationsPage() {
  return (
    <RequireAuth>
      <ComingSoon
        title="Notifications"
        description="Ride requests, confirmations and trip updates will show up here."
        icon={<Bell className="size-7" />}
        sprint={2}
      />
    </RequireAuth>
  );
}
