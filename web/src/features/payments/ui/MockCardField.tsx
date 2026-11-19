"use client";

import { useEffect, useState } from "react";

import { addMockCard } from "@/shared/mocks/payments";

import type { CardFieldProps } from "./cardField";

const DECLINED = "4000000000000002";

/**
 * A stand-in for Stripe's card form when the mock API is on (there's no Stripe account
 * then). Like Stripe's test mode: 4242 4242 4242 4242 is saved, 4000 0000 0000 0002 is
 * declined. Only ever loaded in mock mode.
 */
export function MockCardField({ confirmRef, onChange }: CardFieldProps) {
  const [number, setNumber] = useState("");
  const digits = number.replace(/\D/g, "");

  useEffect(() => {
    confirmRef.current = async () => {
      if (digits === DECLINED) return { error: { code: "card_declined", declineCode: "generic_decline" } };
      addMockCard({ brand: digits.startsWith("5") ? "mastercard" : "visa", last4: digits.slice(-4) });
      return {};
    };
  }, [digits, confirmRef]);

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="mb-1 block font-semibold">Card number</span>
        <input
          inputMode="numeric"
          autoComplete="off"
          value={number}
          onChange={(event) => {
            setNumber(event.target.value);
            onChange({ complete: event.target.value.replace(/\D/g, "").length === 16 });
          }}
          placeholder="4242 4242 4242 4242"
          className="w-full rounded-md border-2 border-line-strong px-4 py-3.5 text-lg outline-none focus:border-ink"
        />
      </label>
      <p className="text-sm text-ink-soft">
        Mock mode, no real Stripe: 4242 4242 4242 4242 is saved, 4000 0000 0000 0002 is declined.
      </p>
    </div>
  );
}
