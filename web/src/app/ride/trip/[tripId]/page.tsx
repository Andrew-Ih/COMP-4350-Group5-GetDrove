import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { fromQueryString, TripDetail } from "@/features/ride";

import { toSearchParams } from "../../searchParams";

export const metadata: Metadata = { title: "Trip · GetDrove" };

/**
 * /ride/trip/{tripId}?lat&lng&direction&time: a trip opened from the results. The search
 * comes along so pickup points can be found near the rider and "All trips" goes back to it.
 */
export default async function TripPage({
  params,
  searchParams,
}: {
  params: Promise<{ tripId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { tripId } = await params;
  const search = fromQueryString(toSearchParams(await searchParams));
  return (
    <RequireAuth>
      <TripDetail tripId={tripId} search={search} />
    </RequireAuth>
  );
}
