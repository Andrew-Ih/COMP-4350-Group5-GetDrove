import type { Metadata } from "next";

import { RequireAuth } from "@/features/auth";
import { AddCard, safeNext } from "@/features/payments";

export const metadata: Metadata = { title: "Payment card · GetDrove" };

/** /account/card, or /account/card?next=/ride/trip/… to go back there after adding a card. */
export default async function PaymentCardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { next } = await searchParams;
  return (
    <RequireAuth>
      <AddCard next={safeNext(typeof next === "string" ? next : undefined)} />
    </RequireAuth>
  );
}
