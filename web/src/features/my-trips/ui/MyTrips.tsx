"use client";

import { ChevronRight, MapPin, Repeat } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { AppHeader, Badge, Button, buttonStyles, Spinner } from "@/shared/ui";

import { useDrivingTrips, useRidingTrips } from "../hooks/useMyTrips";
import {
  canCancel,
  drivingRoute,
  formatMoney,
  formatWhen,
  rideBadge,
  type RiderTrip,
  type Role,
  seatsFilled,
  type Trip,
  tripStatusLabel,
} from "../model/myTrips";
import { CancelTrip } from "./CancelTrip";

const BADGE_VARIANT = { confirmed: "solid", done: "status", pending: "outline", ended: "neutral" } as const;

const TABS: { role: Role; label: string }[] = [
  { role: "rider", label: "Riding" },
  { role: "driver", label: "Driving" },
];

/**
 * My trips (#131): the trips a student is riding on and the ones they've posted, upcoming
 * and past, from GET /api/trips/requests/mine and GET /api/trips/mine. Cancelled trips stay
 * in the list, marked cancelled. A driver can cancel an upcoming trip, or its whole
 * recurring series (#133).
 */
export function MyTrips({ initialRole = "rider" }: { initialRole?: Role }) {
  const me = useCurrentUser();
  const [role, setRole] = useState<Role>(initialRole);

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-2xl px-5 py-8 md:py-12">
        <h1 className="text-3xl md:text-4xl">My trips</h1>

        <div role="tablist" aria-label="Trips as" className="mt-6 flex gap-2 rounded-full bg-surface-muted p-1">
          {TABS.map((tab) => (
            <button
              key={tab.role}
              type="button"
              role="tab"
              id={`tab-${tab.role}`}
              aria-selected={role === tab.role}
              aria-controls={`panel-${tab.role}`}
              onClick={() => setRole(tab.role)}
              className={cn(
                "h-11 flex-1 rounded-full font-bold transition-colors",
                role === tab.role ? "bg-surface text-ink shadow-card" : "text-ink-soft hover:text-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div role="tabpanel" id={`panel-${role}`} aria-labelledby={`tab-${role}`}>
          {role === "rider" ? <Riding /> : <Driving />}
        </div>
      </main>
    </>
  );
}

function Riding() {
  const upcoming = useRidingTrips("upcoming");
  const past = useRidingTrips("past");
  return (
    <>
      <Section title="Upcoming" query={upcoming} empty={<EmptyRides />}>
        {(rides) => rides.map((ride) => <RideRow key={ride.request.id} ride={ride} />)}
      </Section>
      <Section title="Past" query={past} empty={<p className="text-ink-soft">No past rides yet.</p>}>
        {(rides) => rides.map((ride) => <RideRow key={ride.request.id} ride={ride} />)}
      </Section>
    </>
  );
}

function Driving() {
  const upcoming = useDrivingTrips("upcoming");
  const past = useDrivingTrips("past");
  return (
    <>
      <Section title="Upcoming" query={upcoming} empty={<EmptyDrives />}>
        {(trips) => trips.map((trip) => <DriveRow key={trip.id} trip={trip} />)}
      </Section>
      <Section title="Past" query={past} empty={<p className="text-ink-soft">No past trips yet.</p>}>
        {(trips) => trips.map((trip) => <DriveRow key={trip.id} trip={trip} />)}
      </Section>
    </>
  );
}

type ListQuery<T> = { status: "pending" | "error" | "success"; data: T[] | undefined; error: ApiError | null; refetch: () => unknown };

function Section<T>({
  title,
  query,
  empty,
  children,
}: {
  title: string;
  query: ListQuery<T>;
  empty: ReactNode;
  children: (items: T[]) => ReactNode;
}) {
  return (
    <section aria-label={title} className="mt-8">
      <h2 className="text-xl">{title}</h2>
      <div className="mt-3">
        {query.status === "pending" && (
          <p role="status" className="flex items-center gap-3 font-semibold text-ink-soft">
            <Spinner className="size-5" /> Loading…
          </p>
        )}
        {query.status === "error" && <LoadError error={query.error} onRetry={() => void query.refetch()} />}
        {query.status === "success" &&
          (query.data!.length === 0 ? empty : <ul className="space-y-3">{children(query.data!)}</ul>)}
      </div>
    </section>
  );
}

function RideRow({ ride }: { ride: RiderTrip }) {
  const { trip, request } = ride;
  const badge = rideBadge(ride);
  return (
    <li className={cn("rounded-lg border-2 border-line hover:border-line-strong", badge.tone === "ended" && "opacity-70")}>
      <Link href={`/ride/trip/${trip.id}`} className="flex items-center gap-4 p-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-bold">{formatWhen(trip.departureAt)}</p>
            <Badge variant={BADGE_VARIANT[badge.tone]}>{badge.label}</Badge>
          </div>
          <p className="text-ink-soft">{trip.direction === "to_campus" ? "To campus" : "From campus"}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-ink-soft">
            <MapPin aria-hidden="true" className="size-4 shrink-0" />
            <span className="truncate">{request.pickup.label}</span>
          </p>
        </div>
        <span className="shrink-0 text-lg font-extrabold">{formatMoney(request.cost.amountCents)}</span>
        <ChevronRight aria-hidden="true" className="size-5 shrink-0 text-ink-soft" />
      </Link>
    </li>
  );
}

function DriveRow({ trip }: { trip: Trip }) {
  const status = tripStatusLabel(trip);
  return (
    <li aria-label={`Trip ${formatWhen(trip.departureAt)}`} className={cn("rounded-lg border-2 border-line", trip.status === "cancelled" && "opacity-70")}>
      <Link href={`/drive/trips/${trip.id}`} className="flex items-center gap-4 p-4 hover:bg-surface-muted">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-bold">{formatWhen(trip.departureAt)}</p>
            {status && <Badge variant={trip.status === "cancelled" ? "neutral" : "status"}>{status}</Badge>}
            {trip.seriesId && (
              <span className="flex items-center gap-1 text-sm font-semibold text-ink-soft">
                <Repeat aria-hidden="true" className="size-4" /> Repeats
              </span>
            )}
          </div>
          <p className="truncate text-ink-soft">{drivingRoute(trip)}</p>
          {trip.status !== "cancelled" && <p className="text-ink-soft">{seatsFilled(trip)}</p>}
        </div>
        <ChevronRight aria-hidden="true" className="size-5 shrink-0 text-ink-soft" />
      </Link>
      {canCancel(trip) && (
        <div className="border-t border-line px-4 py-3">
          <CancelTrip trip={trip} />
        </div>
      )}
    </li>
  );
}

function EmptyRides() {
  return (
    <div className="space-y-3 text-ink-soft">
      <p>You haven&apos;t asked for a seat on any trips yet.</p>
      <Link href="/ride" className={buttonStyles({ size: "md" })}>
        Find a ride
      </Link>
    </div>
  );
}

function EmptyDrives() {
  return (
    <div className="space-y-3 text-ink-soft">
      <p>You haven&apos;t posted any trips yet.</p>
      <Link href="/drive/new" className={buttonStyles({ size: "md" })}>
        Post a trip
      </Link>
    </div>
  );
}

function LoadError({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  if (error?.code === "unauthorized") {
    return (
      <div role="alert" className="space-y-3 text-ink-soft">
        <p>Your session has ended. Log in again to see your trips.</p>
        <Link href="/login?next=%2Ftrips" className={buttonStyles({ size: "md" })}>
          Log in
        </Link>
      </div>
    );
  }
  return (
    <div role="alert" className="space-y-3 text-ink-soft">
      <p>We couldn&apos;t load these trips. {error?.message}</p>
      <Button size="md" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
