import type { MutableRefObject } from "react";

import type { CardError } from "../model/card";

/** Confirms the card with Stripe for a SetupIntent's client secret. */
export type ConfirmCard = (clientSecret: string) => Promise<{ error?: CardError }>;

/**
 * The card form: Stripe's own (StripeCardField) or, with the mock API on, a stand-in.
 * It reports whether the details are complete, and sets `confirmRef` to the function
 * that sends them to Stripe.
 */
export type CardFieldProps = {
  confirmRef: MutableRefObject<ConfirmCard | null>;
  onChange: (state: { complete: boolean; error?: string }) => void;
};
