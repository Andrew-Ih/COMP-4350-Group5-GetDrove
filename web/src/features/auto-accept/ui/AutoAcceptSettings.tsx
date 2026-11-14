"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { AppHeader, Button, buttonStyles, Spinner } from "@/shared/ui";

import { useAutoAcceptRules, useSaveAutoAcceptRules } from "../hooks/useAutoAccept";
import {
  type AutoAcceptRules,
  buildRules,
  MAX_DETOUR_MINUTES,
  ratingLabel,
  ratingOptions,
  type RulesProblem,
  rulesSummary,
} from "../model/rules";

/**
 * The driver's auto-accept rules (#45), from GET and PUT /api/trips/auto-accept: on or off,
 * the longest detour a pickup may add, and the lowest rating a rider may have. Changes
 * apply to new requests only.
 */
export function AutoAcceptSettings() {
  const me = useCurrentUser();
  const rules = useAutoAcceptRules();

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-xl px-5 py-8 md:py-12">
        <h1 className="text-3xl md:text-4xl">Auto-accept</h1>
        <p className="mt-2 text-ink-soft">Let GetDrove accept riders for you when their request fits your rules.</p>

        {rules.status === "pending" && (
          <p role="status" className="mt-8 flex items-center gap-3 font-semibold text-ink-soft">
            <Spinner className="size-5" /> Loading your rules…
          </p>
        )}
        {rules.status === "error" && <LoadError error={rules.error} onRetry={() => void rules.refetch()} />}
        {/* Starts from what's saved; after a save, `saved` is what was just sent, so nothing's left to save. */}
        {rules.status === "success" && <RulesForm saved={rules.data} />}
      </main>
    </>
  );
}

/** A 422 from the API, on the field it's about. */
function serverProblem(error: ApiError): RulesProblem | undefined {
  const field = error.problem.errors?.find((e) => e.field === "maxDetourMinutes" || e.field === "minRating")?.field;
  if (field === "maxDetourMinutes") return { field, message: `Enter a whole number of minutes from 0 to ${MAX_DETOUR_MINUTES}.` };
  if (field === "minRating") return { field, message: "Choose a rating from 1 to 5, or any rating." };
  return undefined;
}

function RulesForm({ saved }: { saved: AutoAcceptRules }) {
  const save = useSaveAutoAcceptRules();
  const [enabled, setEnabled] = useState(saved.enabled);
  const [minutes, setMinutes] = useState(String(saved.maxDetourMinutes));
  const [minRating, setMinRating] = useState(saved.minRating);
  const [problem, setProblem] = useState<RulesProblem>();
  const [justSaved, setJustSaved] = useState(false);

  const changed = enabled !== saved.enabled || minutes !== String(saved.maxDetourMinutes) || minRating !== saved.minRating;

  function edit<T>(set: (value: T) => void) {
    return (value: T) => {
      set(value);
      setJustSaved(false);
      setProblem(undefined);
    };
  }

  function submit() {
    const built = buildRules({ enabled, maxDetourMinutes: minutes, minRating });
    if ("problem" in built) {
      setProblem(built.problem);
      return;
    }
    setProblem(undefined);
    save.mutate(built.rules, {
      onSuccess: () => setJustSaved(true),
      onError: (error) => setProblem(serverProblem(error)),
    });
  }

  const otherError = save.error && !serverProblem(save.error) ? save.error : undefined;

  return (
    <form
      // Our own checks and messages, instead of the browser's for min/max/step.
      noValidate
      className="mt-8 space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="flex items-center justify-between gap-4 rounded-lg bg-surface-muted px-5 py-4">
        <span id="enabled-label" className="text-lg font-bold">
          Accept requests automatically
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-labelledby="enabled-label"
          onClick={() => edit(setEnabled)(!enabled)}
          className={cn("relative h-7 w-12 shrink-0 rounded-full transition-colors", enabled ? "bg-ink" : "bg-line-strong")}
        >
          <span
            aria-hidden="true"
            className={cn("absolute top-1 left-1 size-5 rounded-full bg-white transition-transform", enabled && "translate-x-5")}
          />
        </button>
      </div>

      {enabled && (
        <>
          <div>
            <label htmlFor="max-detour" className="font-bold">
              Longest detour for a pickup
            </label>
            <div className="mt-2 flex items-center gap-3">
              <input
                id="max-detour"
                type="number"
                inputMode="numeric"
                min={0}
                max={MAX_DETOUR_MINUTES}
                step={1}
                value={minutes}
                aria-invalid={problem?.field === "maxDetourMinutes" || undefined}
                aria-describedby="max-detour-hint"
                onChange={(event) => edit(setMinutes)(event.target.value)}
                className={cn(
                  "h-12 w-24 rounded-md border-2 px-3 text-lg font-bold outline-none focus:border-ink",
                  problem?.field === "maxDetourMinutes" ? "border-danger" : "border-line",
                )}
              />
              <span className="font-semibold">minutes</span>
            </div>
            <p id="max-detour-hint" className="mt-1 text-sm text-ink-soft">
              The extra driving time a rider&apos;s pickup adds to your trip, 0 to {MAX_DETOUR_MINUTES} minutes.
            </p>
          </div>

          <div>
            <p id="min-rating-label" className="font-bold">
              Lowest rider rating
            </p>
            <div role="radiogroup" aria-labelledby="min-rating-label" className="mt-2 flex flex-wrap gap-2">
              {ratingOptions(saved.minRating).map((option) => (
                <button
                  key={option ?? "any"}
                  type="button"
                  role="radio"
                  aria-checked={minRating === option}
                  onClick={() => edit(setMinRating)(option)}
                  className={cn(
                    "h-11 rounded-md border-2 px-4 font-bold transition-colors",
                    minRating === option ? "border-ink bg-ink text-white" : "border-line hover:border-line-strong",
                  )}
                >
                  {option === null ? "Any rating" : `★ ${option.toFixed(1)}+`}
                </button>
              ))}
            </div>
            <p className="mt-1 text-sm text-ink-soft">
              {ratingLabel(minRating)}. New riders without ratings always pass.
            </p>
          </div>
        </>
      )}

      <p className="rounded-lg border-2 border-line px-5 py-4 text-ink-soft">
        {rulesSummary({ enabled, maxDetourMinutes: Number(minutes) || 0, minRating })} Changes apply to new requests only:
        requests already waiting stay as they are.
      </p>

      <div role="alert" className="min-h-5 text-sm font-semibold text-danger">
        {problem?.message}
        {otherError && <SaveError error={otherError} />}
      </div>

      {justSaved && !changed && (
        <p role="status" className="flex items-center gap-2 font-bold text-brand">
          <CheckCircle2 aria-hidden="true" className="size-5" /> Saved
        </p>
      )}

      <Button type="submit" fullWidth loading={save.isPending} disabled={!changed && !problem}>
        {save.isPending ? "Saving…" : "Save"}
      </Button>
    </form>
  );
}

function SaveError({ error }: { error: ApiError }) {
  if (error.code === "unauthorized") {
    return (
      <>
        Your session has ended.{" "}
        <Link href="/login?next=%2Faccount%2Fauto-accept" className="underline">
          Log in
        </Link>{" "}
        to save your rules.
      </>
    );
  }
  return <>We couldn&apos;t save your rules. Try again in a minute.</>;
}

function LoadError({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  if (error?.code === "unauthorized") {
    return (
      <div role="alert" className="mt-8 space-y-4 text-ink-soft">
        <p className="text-lg font-bold text-ink">Your session has ended</p>
        <Link href="/login?next=%2Faccount%2Fauto-accept" className={buttonStyles({ size: "md", fullWidth: true })}>
          Log in
        </Link>
      </div>
    );
  }
  return (
    <div role="alert" className="mt-8 space-y-4 text-ink-soft">
      <p className="text-lg font-bold text-ink">We couldn&apos;t load your rules</p>
      <p>Something went wrong. Try again in a minute.</p>
      <Button size="md" fullWidth onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
