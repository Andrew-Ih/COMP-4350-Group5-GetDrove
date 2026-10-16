import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { fromQueryString, RideHome } from "@/features/ride";

import { toSearchParams } from "./searchParams";

export const metadata: Metadata = { title: "Find a ride · GetDrove" };

/** /ride, or /ride?lat&lng&direction&time to start from a previous search. */
export default async function RidePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const initial = fromQueryString(toSearchParams(await searchParams));
  return (
    <RequireAuth>
      <RideHome initial={initial} />
    </RequireAuth>
  );
}
