import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { fromQueryString, MAX_EXCLUDED_PICKUPS, TripDetail } from "@/features/ride";

import { toSearchParams } from "../../searchParams";

export const metadata: Metadata = { title: "Trip · GetDrove" };

/**
 * /ride/trip/{tripId}?lat&lng&direction&time&exclude: a trip opened from the results. The
 * search comes along so pickup points can be found near the rider and "All trips" goes back
 * to it. `exclude` (repeated) holds the pickup points the rider rejected (#136), so they stay
 * left out after a reload.
 */
export default async function TripPage({
  params,
  searchParams,
}: {
  params: Promise<{ tripId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { tripId } = await params;
  const query = await searchParams;
  const search = fromQueryString(toSearchParams(query));
  const exclude = [query.exclude ?? []].flat().filter((id) => id.length > 0 && id.length <= 64);
  return (
    <RequireAuth>
      <TripDetail tripId={tripId} search={search} exclude={exclude.slice(0, MAX_EXCLUDED_PICKUPS)} />
    </RequireAuth>
  );
}
