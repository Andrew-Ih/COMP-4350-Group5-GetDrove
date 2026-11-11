import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { NotificationsPage } from "@/features/notifications";

export const metadata: Metadata = { title: "Notifications · GetDrove" };

/** /notifications: every notification, newest first (#147). */
export default function Page() {
  return (
    <RequireAuth>
      <NotificationsPage />
    </RequireAuth>
  );
}
