import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { fromQueryString, TripResults } from "@/features/ride";

import { toSearchParams } from "../searchParams";

export const metadata: Metadata = { title: "Trips near you · GetDrove" };

/** /ride/results?lat&lng&direction&time: the search contract's fields, from the rider home. */
export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = fromQueryString(toSearchParams(await searchParams));
  return (
    <RequireAuth>
      <TripResults query={query} />
    </RequireAuth>
  );
}
