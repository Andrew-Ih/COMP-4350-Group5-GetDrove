"use client";

import { AlertTriangle } from "lucide-react";
import { type ReactNode, useState } from "react";

import type { ApiError } from "@/shared/api";
import { Button } from "@/shared/ui";

import { type CancelChoice, useCancelTrip } from "../hooks/useMyTrips";
import { canCancel, formatDay, isLateCancel, type Trip } from "../model/myTrips";

type CancelTripProps = {
  trip: Trip;
  /** After the trip (or its series) was cancelled, with the trips that were. */
  onCancelled?: (cancelled: Trip[]) => void;
  /** After cancelling failed, e.g. the trip started meanwhile (409): time to load it again. */
  onFailed?: () => void;
};

/**
 * Cancel trip, then a confirmation (#133, #273): riders are told; for a recurring trip, just
 * this day or the whole series; a warning within an hour of departure. Shown only while the
 * trip can still be cancelled, so it disappears once it has been. Used in My trips and on
 * the driver's trip page.
 */
export function CancelTrip({ trip, onCancelled, onFailed }: CancelTripProps) {
  const [confirming, setConfirming] = useState(false);
  if (!canCancel(trip)) return null;
  return confirming ? (
    <CancelConfirm trip={trip} onClose={() => setConfirming(false)} onCancelled={onCancelled} onFailed={onFailed} />
  ) : (
    <Button variant="secondary" size="sm" onClick={() => setConfirming(true)}>
      Cancel trip
    </Button>
  );
}

/** What the driver is told when cancelling fails. */
function cancelError(error: ApiError): string {
  if (error.code === "trip_not_cancellable") return "This trip has already started or was cancelled.";
  if (error.code === "trip_not_found" || error.code === "series_not_found") return "This trip no longer exists.";
  return "We couldn't cancel this trip. Try again.";
}

function CancelConfirm({ trip, onClose, onCancelled, onFailed }: CancelTripProps & { onClose: () => void }) {
  const cancel = useCancelTrip();
  const [scope, setScope] = useState<CancelChoice["scope"]>("trip");
  const late = isLateCancel(trip);

  const confirm = () =>
    cancel.mutate(
      { trip, scope },
      {
        onSuccess: (cancelled) => {
          onClose();
          onCancelled?.(cancelled);
        },
        onError: () => onFailed?.(),
      },
    );

  return (
    <div role="group" aria-label="Cancel this trip?" className="space-y-3">
      <p className="font-bold">Cancel this trip?</p>
      <p className="text-ink-soft">Riders on it will be told, and any payment holds on their cards are released.</p>

      {trip.seriesId && (
        <fieldset className="space-y-2">
          <legend className="sr-only">What to cancel</legend>
          <Choice name={`scope-${trip.id}`} checked={scope === "trip"} onChange={() => setScope("trip")}>
            Just this day ({formatDay(trip.departureAt)})
          </Choice>
          <Choice name={`scope-${trip.id}`} checked={scope === "series"} onChange={() => setScope("series")}>
            The whole series (every trip in it that hasn&apos;t started)
          </Choice>
        </fieldset>
      )}

      {late && (
        <p className="flex items-start gap-2 rounded-md bg-surface-muted px-3 py-2 text-sm font-semibold">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          It&apos;s less than an hour before departure, so this is a late cancellation.
        </p>
      )}

      {cancel.error && (
        <p role="alert" className="text-sm font-semibold">
          {cancelError(cancel.error)}
        </p>
      )}

      <div className="flex gap-3">
        <Button variant="secondary" size="sm" onClick={onClose} disabled={cancel.isPending}>
          Keep trip
        </Button>
        <Button variant="dark" size="sm" loading={cancel.isPending} onClick={confirm}>
          {scope === "series" ? "Cancel series" : "Cancel trip"}
        </Button>
      </div>
    </div>
  );
}

function Choice({ name, checked, onChange, children }: { name: string; checked: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-3">
      <input type="radio" name={name} checked={checked} onChange={onChange} className="size-4 accent-ink" />
      <span>{children}</span>
    </label>
  );
}
