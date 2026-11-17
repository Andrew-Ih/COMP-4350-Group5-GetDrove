import type { components } from "@/shared/api/generated/trips";

export type Trip = components["schemas"]["Trip"];
export type RiderTrip = components["schemas"]["RiderTrip"];
export type RequestStatus = components["schemas"]["RequestStatus"];
export type When = "upcoming" | "past";
export type Role = "driver" | "rider";

/** Cancelling less than this long before departure counts as a late cancellation (#134). */
export const LATE_CANCEL_MS = 60 * 60_000;

/** "Thu, Nov 12 · 7:35 AM", in the student's time zone. */
export function formatWhen(iso: string): string {
  const date = new Date(iso);
  const day = date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  const hours = date.getHours();
  const time = `${hours % 12 || 12}:${String(date.getMinutes()).padStart(2, "0")} ${hours < 12 ? "AM" : "PM"}`;
  return `${day} · ${time}`;
}

/** "Thu, Nov 12", for "just this day". */
export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

/**
 * "Wolseley area → U of M Fort Garry" for a driver: their own end (which only they get
 * back) and campus, in the direction of travel.
 */
export function drivingRoute(trip: Trip): string {
  const campus = "U of M Fort Garry";
  const own = (trip.direction === "to_campus" ? trip.origin : trip.destination)?.label ?? "Your spot";
  return trip.direction === "to_campus" ? `${own} → ${campus}` : `${campus} → ${own}`;
}

/** "2 of 3 seats filled". */
export function seatsFilled(trip: Trip): string {
  return `${trip.seatsTotal - trip.seatsAvailable} of ${trip.seatsTotal} seats filled`;
}

/** The trip's own state, when it isn't simply scheduled. */
export function tripStatusLabel(trip: Trip): string | undefined {
  return { scheduled: undefined, in_progress: "Under way", completed: "Completed", cancelled: "Cancelled" }[trip.status];
}

/** A driver can cancel a trip that's scheduled and hasn't left yet. */
export function canCancel(trip: Trip, now: Date = new Date()): boolean {
  return trip.status === "scheduled" && Date.parse(trip.departureAt) > now.getTime();
}

/** Whether cancelling now would count as a late cancellation: less than an hour to departure. */
export function isLateCancel(trip: Trip, now: Date = new Date()): boolean {
  return Date.parse(trip.departureAt) - now.getTime() < LATE_CANCEL_MS;
}

/** confirmed: solid green · done: green tint, like a completed trip on the Driving tab · pending: outline · ended: grey. */
type Badge = { label: string; tone: "confirmed" | "done" | "pending" | "ended" };

/**
 * The badge on a ride: the request's status, or "Trip cancelled" when the driver cancelled
 * the trip (the request is cancelled then too, but the reason is what matters to the rider).
 */
export function rideBadge({ trip, request }: RiderTrip): Badge {
  if (trip.status === "cancelled") return { label: "Trip cancelled", tone: "ended" };
  const labels: Record<RequestStatus, Badge> = {
    pending: { label: "Pending", tone: "pending" },
    accepted: trip.status === "completed" ? { label: "Completed", tone: "done" } : { label: "Confirmed", tone: "confirmed" },
    declined: { label: "Declined", tone: "ended" },
    cancelled: { label: "Cancelled", tone: "ended" },
    expired: { label: "Expired", tone: "ended" },
    payment_failed: { label: "Payment failed", tone: "ended" },
  };
  return labels[request.status];
}

/** 420 → "$4.20". */
export function formatMoney(amountCents: number): string {
  return `$${(amountCents / 100).toFixed(2)}`;
}

/** The trips after a cancellation, so the list shows them as cancelled before it's fetched again. */
export function markCancelled(trips: Trip[], cancelled: Trip[]): Trip[] {
  const byId = new Map(cancelled.map((t) => [t.id, t]));
  return trips.map((t) => byId.get(t.id) ?? t);
}
