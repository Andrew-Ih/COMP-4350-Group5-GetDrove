import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { MyTrips } from "@/features/my-trips";

export const metadata: Metadata = { title: "My trips · GetDrove" };

/** /trips, or /trips?role=driver to open on the trips the student is driving. */
export default async function MyTripsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { role } = await searchParams;
  return (
    <RequireAuth>
      <MyTrips initialRole={role === "driver" ? "driver" : "rider"} />
    </RequireAuth>
  );
}
