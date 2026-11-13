"use client";

import { CardElement, Elements, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import { useEffect } from "react";

import { stripePublishableKey } from "@/shared/config/env";

import type { CardFieldProps } from "./cardField";

// Loaded once, the first time the form is shown. Stripe's script must come from Stripe.
let stripePromise: Promise<Stripe | null> | undefined;
function getStripe() {
  stripePromise ??= loadStripe(stripePublishableKey);
  return stripePromise;
}

/**
 * Stripe's card form (Stripe Elements). Card details go straight from this form to Stripe;
 * they never reach GetDrove's code or servers.
 */
export function StripeCardField(props: CardFieldProps) {
  return (
    <Elements stripe={getStripe()}>
      <Field {...props} />
    </Elements>
  );
}

function Field({ confirmRef, onChange }: CardFieldProps) {
  const stripe = useStripe();
  const elements = useElements();

  useEffect(() => {
    confirmRef.current = async (clientSecret) => {
      const card = elements?.getElement(CardElement);
      if (!stripe || !card) return { error: { message: "The card form is still loading. Try again in a moment." } };
      const result = await stripe.confirmCardSetup(clientSecret, { payment_method: { card } });
      if (!result.error) return {};
      return { error: { code: result.error.code, declineCode: result.error.decline_code, message: result.error.message } };
    };
  }, [stripe, elements, confirmRef]);

  return (
    <div className="rounded-md border-2 border-line-strong bg-surface px-4 py-4 focus-within:border-ink">
      <CardElement
        options={{
          style: {
            base: { fontSize: "17px", color: "#111111", fontFamily: "Figtree, system-ui, sans-serif", "::placeholder": { color: "#7a7f79" } },
            invalid: { color: "#b42318" },
          },
        }}
        onChange={(event) => onChange({ complete: event.complete, error: event.error?.message })}
      />
    </div>
  );
}
