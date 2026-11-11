import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { TripRequests } from "@/features/drive";

export const metadata: Metadata = { title: "Your trip · GetDrove" };

/** /drive/trips/{tripId}: one of the driver's trips, with its pending requests. */
export default async function DriverTripPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return (
    <RequireAuth>
      <TripRequests tripId={tripId} />
    </RequireAuth>
  );
}
