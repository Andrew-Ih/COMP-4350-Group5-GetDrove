"use client";

import { AlertCircle, CheckCircle2, CreditCard } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { type ComponentType, type ReactNode, useRef, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { apiMocking, stripePublishableKey } from "@/shared/config/env";
import { AppHeader, Button, buttonStyles, Card, PrivacyNote, Spinner } from "@/shared/ui";

import { createSetupIntent } from "../api/paymentsApi";
import { usePaymentMethods } from "../hooks/usePaymentCard";
import { cardErrorMessage, cardExpiry, cardLabel, defaultCard, type PaymentMethod } from "../model/card";
import type { CardFieldProps, ConfirmCard } from "./cardField";
import { StripeCardField } from "./StripeCardField";

// With the mock API on there's no Stripe account, so a stand-in form is used. It's only
// loaded then, so it never reaches the real site.
const CardField: ComponentType<CardFieldProps> = apiMocking
  ? dynamic(() => import("./MockCardField").then((m) => m.MockCardField), { ssr: false })
  : StripeCardField;

/** How long to wait between checks for the new card, and how many times to check. */
const CHECK_EVERY_MS = 1000;
const CHECKS = 5;
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Phase = { name: "idle" } | { name: "sending" } | { name: "saving" } | { name: "saved" } | { name: "slow" } | { name: "failed"; message: string };

/**
 * Add a payment card (#152), with Stripe's own form. The card is saved with a SetupIntent
 * (POST /api/payments/setup-intent, then stripe.confirmCardSetup) and read back from
 * GET /api/payments/methods, which lists it once Stripe has it. `next` is where the student
 * came from (e.g. a trip they were requesting), to go back to afterwards.
 */
export function AddCard({ next }: { next: string | undefined }) {
  const me = useCurrentUser();
  const methods = usePaymentMethods();
  const [adding, setAdding] = useState(false);
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const card = defaultCard(methods.data ?? []);
  const showForm = methods.status === "success" && (!card || adding) && phase.name !== "saved";

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-xl px-5 py-8 md:py-12">
        <h1 className="text-3xl md:text-4xl">Payment card</h1>
        <p className="mt-2 text-ink-soft">
          Your card is only charged for rides a driver accepted, and only after the trip.
        </p>

        {methods.status === "pending" && (
          <p role="status" className="mt-8 flex items-center gap-3 font-semibold text-ink-soft">
            <Spinner className="size-5" /> Loading your card…
          </p>
        )}
        {methods.status === "error" && <LoadError error={methods.error} onRetry={() => void methods.refetch()} />}

        {phase.name === "saved" && card && (
          <div role="status" className="mt-8 flex gap-3 rounded-lg border-2 border-brand bg-brand-tint px-5 py-4">
            <CheckCircle2 aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-brand" />
            <div>
              <p className="text-lg font-bold text-brand">Card saved</p>
              <p className="text-ink-soft">You can ask for seats on trips now.</p>
            </div>
          </div>
        )}

        {methods.status === "success" && card && !showForm && (
          <SavedCard card={card} next={next} onChange={() => {
            setPhase({ name: "idle" });
            setAdding(true);
          }} />
        )}

        {showForm &&
          (apiMocking || stripePublishableKey ? (
            <CardForm
              replacing={Boolean(card)}
              phase={phase}
              setPhase={setPhase}
              onCancel={card ? () => setAdding(false) : undefined}
              onSaved={async (before) => {
                // Stripe has the card; wait until the list shows it (usually straight away).
                for (let i = 0; i < CHECKS; i++) {
                  const { data } = await methods.refetch();
                  if (data?.some((m) => !before.has(m.id))) {
                    setAdding(false);
                    setPhase({ name: "saved" });
                    return;
                  }
                  await wait(CHECK_EVERY_MS);
                }
                setPhase({ name: "slow" });
              }}
              existing={methods.data ?? []}
            />
          ) : (
            <p role="alert" className="mt-8 rounded-lg border-2 border-line px-5 py-4 text-ink-soft">
              Adding a card isn&apos;t set up on this site yet.
            </p>
          ))}

      </main>
    </>
  );
}

function SavedCard({ card, next, onChange }: { card: PaymentMethod; next: string | undefined; onChange: () => void }) {
  return (
    <div className="mt-8 space-y-4">
      <Card className="flex items-center gap-4 p-5">
        <span aria-hidden="true" className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface-muted">
          <CreditCard className="size-6" />
        </span>
        <div>
          <p className="text-lg font-bold">{cardLabel(card)}</p>
          <p className="text-ink-soft">{cardExpiry(card)}</p>
        </div>
      </Card>
      {next ? (
        <Link href={next} className={buttonStyles({ fullWidth: true })}>
          Back to your trip
        </Link>
      ) : (
        <Link href="/ride" className={buttonStyles({ fullWidth: true })}>
          Find a ride
        </Link>
      )}
      <Button variant="secondary" fullWidth size="md" onClick={onChange}>
        Use a different card
      </Button>
    </div>
  );
}

function CardForm({
  replacing,
  phase,
  setPhase,
  onCancel,
  onSaved,
  existing,
}: {
  replacing: boolean;
  phase: Phase;
  setPhase: (phase: Phase) => void;
  onCancel: (() => void) | undefined;
  onSaved: (before: Set<string>) => Promise<void>;
  existing: PaymentMethod[];
}) {
  const confirmRef = useRef<ConfirmCard | null>(null);
  const [field, setField] = useState<{ complete: boolean; error?: string }>({ complete: false });
  const busy = phase.name === "sending" || phase.name === "saving";

  async function save() {
    const confirm = confirmRef.current;
    if (!confirm) return;
    const before = new Set(existing.map((m) => m.id));
    setPhase({ name: "sending" });
    let clientSecret: string;
    try {
      ({ clientSecret } = await createSetupIntent());
    } catch (error) {
      const unavailable = (error as ApiError).code === "payments_unavailable";
      setPhase({
        name: "failed",
        message: unavailable ? "Card payments are unavailable right now. Try again in a minute." : "We couldn't start saving your card. Try again.",
      });
      return;
    }
    const result = await confirm(clientSecret);
    if (result.error) {
      setPhase({ name: "failed", message: cardErrorMessage(result.error) });
      return;
    }
    setPhase({ name: "saving" });
    await onSaved(before);
  }

  return (
    <form
      className="mt-8 space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <h2 className="text-xl">{replacing ? "Add a different card" : "Add a card"}</h2>
      <CardField
        confirmRef={confirmRef}
        onChange={(state) => {
          setField(state);
          if (phase.name === "failed") setPhase({ name: "idle" });
        }}
      />
      {field.error && <p className="text-sm font-semibold text-danger">{field.error}</p>}
      {phase.name === "failed" && (
        <p role="alert" className="flex items-start gap-2 rounded-md bg-danger-tint px-4 py-3 font-semibold text-danger">
          <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          {phase.message}
        </p>
      )}
      {phase.name === "slow" && (
        <Notice>Your card was added, but it&apos;s taking a moment to show up. Refresh the page in a minute.</Notice>
      )}
      <Button type="submit" fullWidth disabled={!field.complete || busy} loading={busy}>
        {phase.name === "saving" ? "Saving…" : "Save card"}
      </Button>
      {onCancel && (
        <Button type="button" variant="secondary" size="md" fullWidth onClick={onCancel} disabled={busy}>
          Keep my current card
        </Button>
      )}
      <PrivacyNote>Card details go straight to Stripe, our payment provider. GetDrove never sees or stores them.</PrivacyNote>
    </form>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="rounded-md bg-surface-muted px-4 py-3 text-ink-soft">
      {children}
    </p>
  );
}

function LoadError({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  if (error?.code === "unauthorized") {
    return (
      <div role="alert" className="mt-8 space-y-3 text-ink-soft">
        <p>Your session has ended. Log in again to manage your card.</p>
        <Link href="/login?next=%2Faccount%2Fcard" className={buttonStyles({ size: "md" })}>
          Log in
        </Link>
      </div>
    );
  }
  const unavailable = error?.code === "payments_unavailable" || error?.code === "service_unavailable";
  return (
    <div role="alert" className="mt-8 space-y-3 text-ink-soft">
      <p>{unavailable ? "Card payments are unavailable right now. Try again in a minute." : "We couldn't load your card."}</p>
      <Button size="md" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
