"use client";

import { AlertTriangle, MapPin } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, type MapRoute, MapView } from "@/shared/map";
import { AppHeader, Avatar, Button, buttonStyles, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { useDecideRequest, useDriverRoute, useDriverTrip, useTripRequests } from "../hooks/useTripRequests";
import { formatClock, type Trip } from "../model/postTrip";
import {
  canDecide,
  departureLine,
  type DriverRequest,
  formatDetour,
  pickupOrderLabel,
  riderLine,
  routeLine,
  seatsFilled,
  seatsLeftLine,
  splitRequests,
} from "../model/requests";

/**
 * The driver's pending requests for one of their trips (#142): each with the rider's rating,
 * no-shows, pickup point and the detour it adds (#40), and Accept and Decline. The detour
 * comes with the list from GET /api/trips/{id}/requests; when routing couldn't work it out,
 * the request says so with a retry instead of showing a number (#39). Drivers only ever see
 * pickup points, never where riders live (#32).
 */
export function TripRequests({ tripId }: { tripId: string }) {
  const me = useCurrentUser();
  const detail = useDriverTrip(tripId);
  const requests = useTripRequests(tripId);
  const route = useDriverRoute(tripId, detail.isSuccess);
  const trip = detail.data?.trip;
  const { pending, accepted } = useMemo(() => splitRequests(requests.data ?? []), [requests.data]);

  const markers = useMemo<MapMarker[]>(() => {
    if (!trip) return [];
    const list: MapMarker[] = [];
    const driverEnd = trip.direction === "to_campus" ? trip.origin : trip.destination;
    const campus = (trip.direction === "to_campus" ? trip.destination : trip.origin) ?? undefined;
    if (driverEnd) {
      const label = trip.direction === "to_campus" ? `Start · ${formatClock(trip.departureAt)}` : "Your stop";
      list.push({ id: "driver-end", lngLat: [driverEnd.lng, driverEnd.lat], kind: "you", label });
    }
    list.push({ id: "campus", lngLat: campus ? [campus.lng, campus.lat] : CAMPUS, kind: "campus", label: campus?.label ?? "University Centre" });
    for (const r of accepted) {
      list.push({ id: `accepted-${r.id}`, lngLat: [r.pickup.lng, r.pickup.lat], kind: "accepted", label: `${r.rider.firstName} · accepted` });
    }
    for (const r of pending) {
      const detour = formatDetour(r.detourSeconds);
      list.push({ id: `pending-${r.id}`, lngLat: [r.pickup.lng, r.pickup.lat], kind: "stop", label: detour ? `${r.rider.firstName} · ${detour}` : r.rider.firstName });
    }
    return list;
  }, [trip, pending, accepted]);

  const mapRoutes = useMemo<MapRoute[]>(
    () => (route.data ? [{ id: "trip", coordinates: route.data.geometry.coordinates.map(([lng, lat]) => [lng, lat] as LngLat), style: "primary" }] : []),
    [route.data],
  );

  // The map fits the trip and its pickups when they load. The key only changes then, so
  // accepting or declining doesn't move the map.
  const fitKey = trip ? `${trip.id}:${requests.isSuccess ? "requests" : "trip"}` : undefined;
  const fitTo = useMemo(
    () => (fitKey && markers.length > 1 ? { key: fitKey, points: markers.map((m) => m.lngLat) } : undefined),
    [fitKey, markers],
  );

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <MapLayout
        map={<MapView routes={mapRoutes} markers={markers} fitTo={fitTo} />}
        panel={
          <>
            {detail.status === "pending" && <Loading>Loading your trip…</Loading>}
            {detail.status === "error" && <LoadError error={detail.error} onRetry={() => void detail.refetch()} what="this trip" />}
            {trip && (
              <>
                <TripCard trip={trip} accepted={accepted} />
                <Requests
                  trip={trip}
                  tripId={tripId}
                  status={requests.status}
                  error={requests.error}
                  onRetry={() => void requests.refetch()}
                  refreshing={requests.isFetching}
                  pending={pending}
                  accepted={accepted}
                />
              </>
            )}
            <PrivacyNote className="mt-8">You see each rider&apos;s pickup point, never their home address.</PrivacyNote>
          </>
        }
      />
    </>
  );
}

function TripCard({ trip, accepted }: { trip: Trip; accepted: DriverRequest[] }) {
  const filled = trip.seatsTotal - trip.seatsAvailable;
  const names = accepted.map((r) => r.rider.firstName).join(", ");
  return (
    <div className="rounded-lg bg-ink px-6 py-5 text-white">
      <p className="text-sm font-semibold text-white/80">{departureLine(trip)}</p>
      <h1 className="mt-1 text-2xl leading-tight">{routeLine(trip)}</h1>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span aria-hidden="true" className="flex gap-1.5">
          {Array.from({ length: trip.seatsTotal }, (_, i) => (
            <span key={i} className={cn("h-2 w-8 rounded-full", i < filled ? "bg-brand-light" : "bg-white/30")} />
          ))}
        </span>
        <span className="font-bold">{seatsFilled(trip)}</span>
        {names && <span className="text-white/80">· {names}</span>}
      </div>
    </div>
  );
}

type RequestsProps = {
  trip: Trip;
  tripId: string;
  status: "pending" | "error" | "success";
  error: ApiError | null;
  onRetry: () => void;
  refreshing: boolean;
  pending: DriverRequest[];
  accepted: DriverRequest[];
};

function Requests({ trip, tripId, status, error, onRetry, refreshing, pending, accepted }: RequestsProps) {
  const decidable = canDecide(trip);

  if (status === "pending") return <Loading>Loading requests…</Loading>;
  if (status === "error") return <LoadError error={error} onRetry={onRetry} what="the requests" />;

  return (
    <>
      <div className="mt-8 flex items-baseline justify-between gap-3">
        <h2 className="text-2xl leading-tight">
          {pending.length === 0 ? "No pending requests" : `${pending.length} pending ${pending.length === 1 ? "request" : "requests"}`}
        </h2>
        <p className={cn("shrink-0 font-semibold", trip.seatsAvailable === 0 ? "text-ink" : "text-ink-soft")}>{seatsLeftLine(trip)}</p>
      </div>

      {!decidable && (
        <p className="mt-2 text-ink-soft">
          {trip.status === "cancelled" ? "This trip was cancelled." : "This trip has already left, so requests can't be changed."}
        </p>
      )}

      {pending.length === 0 ? (
        <p className="mt-2 text-ink-soft">Riders whose area is along your route can request a seat. Their requests show up here.</p>
      ) : (
        <ul aria-label="Pending requests" className="mt-4 space-y-3">
          {pending.map((request) => (
            <RequestCard
              key={request.id}
              tripId={tripId}
              request={request}
              decidable={decidable}
              full={trip.seatsAvailable === 0}
              onRetryDetour={onRetry}
              refreshing={refreshing}
            />
          ))}
        </ul>
      )}

      {accepted.length > 0 && (
        <>
          <h2 className="mt-8 text-xl">Riding with you</h2>
          <ul aria-label="Accepted riders" className="mt-3 divide-y divide-line">
            {accepted.map((r) => (
              <li key={r.id} className="flex items-center gap-3 py-3">
                <Avatar name={r.rider.firstName} size="sm" tone="soft" />
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{r.rider.firstName}</p>
                  <p className="truncate text-sm text-ink-soft">{r.pickup.label}</p>
                </div>
                {pickupOrderLabel(r.pickupOrder) && <span className="shrink-0 text-sm font-semibold text-brand">{pickupOrderLabel(r.pickupOrder)}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

/** What the driver is told when accepting or declining fails. */
function decisionError(error: ApiError, decision: "accepted" | "declined"): string {
  if (error.code === "seat_taken") return "Your trip is full now, so this request can't be accepted.";
  if (error.code === "request_not_pending" || error.code === "request_not_decidable") {
    return "This request has changed: the rider may have cancelled it. The list has been updated.";
  }
  return decision === "accepted" ? "We couldn't accept this request. Try again." : "We couldn't decline this request. Try again.";
}

function RequestCard({
  tripId,
  request,
  decidable,
  full,
  onRetryDetour,
  refreshing,
}: {
  tripId: string;
  request: DriverRequest;
  decidable: boolean;
  full: boolean;
  onRetryDetour: () => void;
  refreshing: boolean;
}) {
  const decide = useDecideRequest(tripId);
  const [choice, setChoice] = useState<"accepted" | "declined">();
  const detour = formatDetour(request.detourSeconds);
  const name = request.rider.firstName;

  return (
    <li aria-label={`Request from ${name}`} className="rounded-lg border-2 border-line p-4">
      <div className="flex items-start gap-3">
        <Avatar name={name} />
        <div className="min-w-0 flex-1">
          <p>
            <span className="text-lg font-bold">{name}</span> <span className="text-ink-soft">{riderLine(request.rider)}</span>
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-ink-soft">
            <MapPin aria-hidden="true" className="size-4 shrink-0" />
            <span className="truncate">{request.pickup.label}</span>
          </p>
        </div>
        {detour ? (
          <span className="shrink-0 rounded-full bg-ink px-3.5 py-1.5 text-lg font-extrabold text-white" aria-label={`Detour ${detour}`}>
            {detour}
          </span>
        ) : refreshing ? (
          <span role="status" className="flex shrink-0 items-center gap-2 rounded-full bg-surface-muted px-3.5 py-1.5 font-semibold">
            <Spinner className="size-4" /> Calculating…
          </span>
        ) : null}
      </div>

      {!detour && !refreshing && (
        <p className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
          <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-ink" />
          <span>
            Couldn&apos;t work out the detour.{" "}
            <button type="button" onClick={onRetryDetour} className="font-bold text-ink underline underline-offset-2">
              Try again
            </button>
          </span>
        </p>
      )}

      {decide.error && (
        <p role="alert" className="mt-3 text-sm font-semibold text-ink">
          {decisionError(decide.error, choice ?? "accepted")}
        </p>
      )}

      {decidable && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Button
            variant="secondary"
            size="md"
            disabled={decide.isPending}
            loading={decide.isPending && choice === "declined"}
            onClick={() => {
              setChoice("declined");
              decide.mutate({ requestId: request.id, decision: "declined" });
            }}
            aria-label={`Decline ${name}`}
          >
            Decline
          </Button>
          <Button
            size="md"
            disabled={decide.isPending || full}
            loading={decide.isPending && choice === "accepted"}
            onClick={() => {
              setChoice("accepted");
              decide.mutate({ requestId: request.id, decision: "accepted" });
            }}
            aria-label={`Accept ${name}`}
          >
            Accept
          </Button>
        </div>
      )}
    </li>
  );
}

function Loading({ children }: { children: ReactNode }) {
  return (
    <p className="mt-10 flex items-center justify-center gap-3 font-semibold text-ink-soft" role="status">
      <Spinner className="size-5" /> {children}
    </p>
  );
}

function LoadError({ error, onRetry, what }: { error: ApiError | null; onRetry: () => void; what: string }) {
  const code = error?.code;

  if (code === "unauthorized") {
    const next = typeof window === "undefined" ? "/drive/new" : `${window.location.pathname}${window.location.search}`;
    return (
      <Message title="Your session has ended">
        <p>Log in again to see your trip.</p>
        <Link href={`/login?next=${encodeURIComponent(next)}`} className={buttonStyles({ size: "md", fullWidth: true })}>
          Log in
        </Link>
      </Message>
    );
  }
  if (code === "not_trip_driver") {
    return (
      <Message title="This isn't your trip">
        <p>Only the driver who posted a trip can see its requests.</p>
        <Link href="/drive/new" className={buttonStyles({ size: "md", fullWidth: true })}>
          Post a trip
        </Link>
      </Message>
    );
  }
  if (code === "trip_not_found" || code === "invalid_input") {
    return (
      <Message title="This trip no longer exists">
        <p>It may have been cancelled.</p>
        <Link href="/drive/new" className={buttonStyles({ size: "md", fullWidth: true })}>
          Post a trip
        </Link>
      </Message>
    );
  }
  return (
    <Message title={`We couldn't load ${what}`}>
      <p>{error?.message}</p>
      <Button size="md" fullWidth onClick={onRetry}>
        Try again
      </Button>
    </Message>
  );
}

function Message({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div role="alert" className="mt-8 space-y-4 text-ink-soft">
      <h1 className="text-2xl leading-tight text-ink">{title}</h1>
      {children}
    </div>
  );
}
