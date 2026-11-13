"use client";

import { ArrowLeft, CheckCircle2, Clock, Footprints, XCircle } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, type MapRoute, MapView } from "@/shared/map";
import { AppHeader, Avatar, Button, buttonStyles, Eyebrow, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { useCancelSeatRequest, useProfile, useRequestSeat, useRoute, useSeatRequest, useTripDetail } from "../hooks/useTripDetail";
import { formatClock, formatMoney, formatWalk, routeCoordinates } from "../model/results";
import { AREA_RADIUS_METERS, type SearchQuery, toQueryString } from "../model/search";
import {
  availability,
  cancelRequestError,
  type DriverProfile,
  driverLine,
  isActive,
  type PickupOption,
  requestOutcome,
  requestSeatError,
  type SeatRequest,
  seatsAndDeparture,
  type TripDetail as Detail,
} from "../model/tripDetail";

/**
 * A trip opened from the results (#140): the driver, the pickup point and the rider's
 * share, from GET /api/trips/{id}?lat&lng. The rider can pick another of the (up to 3)
 * pickup points (#136). `search` is the search the rider came from: its location is used
 * to find pickup points, and "All trips" goes back to its results. Without it, the trip
 * shows without pickup points.
 *
 * Requesting a seat (#141): the request is sent with the chosen pickup, then checked every
 * few seconds while it's pending, so the screen shows when the driver accepts or declines.
 * The rider can cancel a pending or accepted request.
 */
export function TripDetail({ tripId, search }: { tripId: string; search: SearchQuery | undefined }) {
  const me = useCurrentUser();
  const rider = useMemo(() => (search ? { lat: search.lat, lng: search.lng } : undefined), [search]);
  const detail = useTripDetail(tripId, rider);
  const trip = detail.data?.trip;
  const profile = useProfile(trip?.driverId);
  const route = useRoute(tripId, detail.isSuccess);

  const pickups = useMemo(() => detail.data?.pickups ?? [], [detail.data]);
  const [chosenId, setChosenId] = useState<string>();

  // The rider's request: the one just sent, or the one the trip detail came with. It's
  // checked again while pending; a declined or cancelled one stays on screen until another is sent.
  const [sentId, setSentId] = useState<string>();
  const myRequest = detail.data?.myRequest ?? undefined;
  const seatRequest = useSeatRequest(sentId ?? myRequest?.id, myRequest);
  const current = seatRequest.data ?? myRequest;
  const active = isActive(current) ? current : undefined;

  // When the driver decides, fetch the trip again for the seats left and, once accepted, the car.
  const queryClient = useQueryClient();
  const lastStatus = useRef(current?.status);
  useEffect(() => {
    if (lastStatus.current === "pending" && current?.status && current.status !== "pending") {
      void queryClient.invalidateQueries({ queryKey: ["trips", "detail", tripId] });
    }
    lastStatus.current = current?.status;
  }, [current?.status, queryClient, tripId]);

  // Once the rider has asked for a seat, their request's pickup point and price are the ones that count.
  const pickup = useMemo<PickupOption | undefined>(
    () => (active ? { ...active.pickup, id: "my-request", cost: active.cost } : (pickups.find((p) => p.id === chosenId) ?? pickups[0])),
    [active, pickups, chosenId],
  );

  const you = useMemo<LngLat | undefined>(() => (rider ? [rider.lng, rider.lat] : undefined), [rider]);
  const area = useMemo(() => (you ? { center: you, radiusMeters: AREA_RADIUS_METERS } : undefined), [you]);
  const campus = (trip?.direction === "from_campus" ? trip.origin : trip?.destination) ?? undefined;

  const markers = useMemo<MapMarker[]>(() => {
    const list: MapMarker[] = [
      { id: "campus", lngLat: campus ? [campus.lng, campus.lat] : CAMPUS, kind: "campus", label: campus?.label ?? "University Centre" },
    ];
    // The other points as plain dots: they're often close together, so their labels would
    // overlap. The panel lists them by name.
    for (const option of active ? [] : pickups) {
      if (option.id !== pickup?.id) list.push({ id: `option-${option.id}`, lngLat: [option.lng, option.lat], kind: "stop" });
    }
    if (pickup) list.push({ id: "pickup", lngLat: [pickup.lng, pickup.lat], kind: "pickup", label: pickup.label });
    if (you) list.push({ id: "you", lngLat: you, kind: "you", label: "You" });
    return list;
  }, [campus, active, pickups, pickup, you]);

  const mapRoutes = useMemo<MapRoute[]>(() => {
    const list: MapRoute[] = [];
    if (route.data) list.push({ id: "trip", coordinates: routeCoordinates(route.data), style: "primary" });
    // A straight dotted line, like on the results: not the exact walking path.
    if (pickup && you) list.push({ id: "walk", coordinates: [you, [pickup.lng, pickup.lat]], style: "walk" });
    return list;
  }, [route.data, pickup, you]);

  // Fit the rider, campus and every pickup point once, so switching pickups doesn't move the map.
  const fitTo = useMemo(() => {
    if (!detail.data) return undefined;
    const points: LngLat[] = [CAMPUS, ...pickups.map((p): LngLat => [p.lng, p.lat])];
    if (you) points.push(you);
    return { key: `${tripId}:${pickups.map((p) => p.id).join(",")}`, points };
  }, [detail.data, pickups, you, tripId]);

  const back = search
    ? { href: `/ride/results?${toQueryString(search)}`, label: "All trips" }
    : { href: "/ride", label: "Find a ride" };

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <MapLayout
        map={<MapView routes={mapRoutes} markers={markers} area={area} fitTo={fitTo} />}
        panel={
          <>
            <Link href={back.href} className="inline-flex items-center gap-3 font-bold">
              <span className="flex size-12 items-center justify-center rounded-full bg-surface-muted hover:bg-line">
                <ArrowLeft aria-hidden="true" className="size-5" />
              </span>
              {back.label}
            </Link>

            {detail.status === "pending" && (
              <p className="mt-10 flex items-center justify-center gap-3 font-semibold text-ink-soft" role="status">
                <Spinner className="size-5" /> Loading trip…
              </p>
            )}

            {detail.status === "error" && (
              <DetailError error={detail.error} onRetry={() => void detail.refetch()} back={back} />
            )}

            {detail.status === "success" && (
              <Trip
                tripId={tripId}
                detail={detail.data}
                profile={profile.data}
                pickup={pickup}
                onChoosePickup={setChosenId}
                rider={rider}
                request={current}
                onSent={(request) => setSentId(request.id)}
                back={back}
              />
            )}
          </>
        }
      />
    </>
  );
}

type Back = { href: string; label: string };

function Trip({
  tripId,
  detail,
  profile,
  pickup,
  onChoosePickup,
  rider,
  request,
  onSent,
  back,
}: {
  tripId: string;
  detail: Detail;
  profile: DriverProfile | undefined;
  pickup: PickupOption | undefined;
  onChoosePickup: (id: string) => void;
  rider: { lat: number; lng: number } | undefined;
  request: SeatRequest | undefined;
  onSent: (request: SeatRequest) => void;
  back: Back;
}) {
  const { trip, vehicle, pickups } = detail;
  const [choosing, setChoosing] = useState(false);
  const state = availability(trip);
  const name = profile?.firstName;

  if (state === "cancelled" || state === "departed") {
    return (
      <Message title={state === "cancelled" ? "This trip was cancelled" : "This trip has already left"}>
        <p>Look for another trip at a similar time.</p>
        <Link href={back.href} className={buttonStyles({ size: "md", fullWidth: true })}>
          {back.label}
        </Link>
      </Message>
    );
  }

  const toCampus = trip.direction === "to_campus";
  const campus = (toCampus ? trip.destination : trip.origin) ?? { label: "University Centre" };
  const nearYou = pickup && (
    <NearYouStop
      pickup={pickup}
      toCampus={toCampus}
      canChoose={pickups.length > 1 && !isActive(request)}
      choosing={choosing}
      onToggle={() => setChoosing((open) => !open)}
    />
  );
  const campusStop = (
    <Stop
      icon="square"
      eyebrow={toCampus ? `Drop-off · ${formatClock(trip.estimatedArrivalAt)}` : `Pickup · ${formatClock(trip.departureAt)}`}
      title={campus.label}
    />
  );

  return (
    <>
      <div className="mt-6 flex items-center gap-4 border-b border-line pb-6">
        <Avatar name={name ?? "Driver"} tone="soft" size="lg" />
        <div className="min-w-0">
          <h1 className="text-3xl leading-tight">{name ?? "Your driver"}</h1>
          {driverLine(profile, vehicle) && <p className="font-semibold">{driverLine(profile, vehicle)}</p>}
          <p className="text-ink-soft">{seatsAndDeparture(trip)}</p>
        </div>
      </div>

      {pickup ? (
        <>
          <ol aria-label="Stops" className="mt-6 space-y-6">
            {toCampus ? (
              <>
                {nearYou}
                {campusStop}
              </>
            ) : (
              <>
                {campusStop}
                {nearYou}
              </>
            )}
          </ol>
          {choosing && (
            <PickupChoices
              pickups={pickups}
              chosen={pickup}
              onChoose={(id) => {
                onChoosePickup(id);
                setChoosing(false);
              }}
            />
          )}
          <Share pickup={pickup} />
          <RequestArea
            tripId={tripId}
            state={state}
            vehicle={vehicle}
            pickup={pickup}
            rider={rider}
            request={request}
            onSent={onSent}
            name={name}
            back={back}
          />
        </>
      ) : (
        <NoPickup hasSearch={Boolean(rider)} back={back} />
      )}
    </>
  );
}

function Stop({ icon, eyebrow, title, children }: { icon: "circle" | "square"; eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <li className="flex gap-4">
      <span
        aria-hidden="true"
        className={cn("mt-1 size-5 shrink-0 border-[5px] border-ink bg-white", icon === "circle" ? "rounded-full" : "rounded-[3px]")}
      />
      <div className="min-w-0">
        <Eyebrow tone={icon === "circle" ? "brand" : "muted"}>{eyebrow}</Eyebrow>
        <p className="text-xl font-bold">{title}</p>
        {children}
      </div>
    </li>
  );
}

function NearYouStop({
  pickup,
  toCampus,
  canChoose,
  choosing,
  onToggle,
}: {
  pickup: PickupOption;
  toCampus: boolean;
  canChoose: boolean;
  choosing: boolean;
  onToggle: () => void;
}) {
  return (
    <Stop icon="circle" eyebrow={toCampus ? "Pickup" : "Drop-off"} title={pickup.label}>
      <p className="mt-0.5 flex items-center gap-1.5 text-ink-soft">
        <Footprints aria-hidden="true" className="size-4 shrink-0" />
        {formatWalk(pickup.walkSeconds)} {toCampus ? "from" : "to"} your area
      </p>
      {canChoose ? (
        <button type="button" aria-expanded={choosing} onClick={onToggle} className="mt-2 font-bold underline underline-offset-4">
          {choosing ? "Keep this point" : `Choose a different ${toCampus ? "pickup" : "drop-off"} point`}
        </button>
      ) : null}
    </Stop>
  );
}

function PickupChoices({
  pickups,
  chosen,
  onChoose,
}: {
  pickups: PickupOption[];
  chosen: PickupOption;
  onChoose: (id: string) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Points near you" className="mt-4 space-y-2">
      {pickups.map((option) => (
        <button
          key={option.id}
          type="button"
          role="radio"
          aria-checked={option.id === chosen.id}
          onClick={() => onChoose(option.id)}
          className={cn(
            "flex w-full items-center justify-between gap-3 rounded-md border-2 bg-surface px-4 py-3 text-left",
            option.id === chosen.id ? "border-ink" : "border-line hover:border-line-strong",
          )}
        >
          <span className="min-w-0">
            <span className="block truncate font-bold">{option.label}</span>
            <span className="block text-sm text-ink-soft">{formatWalk(option.walkSeconds)}</span>
          </span>
          <span className="shrink-0 font-bold">{option.cost ? formatMoney(option.cost.amountCents) : "—"}</span>
        </button>
      ))}
    </div>
  );
}

function Share({ pickup }: { pickup: PickupOption }) {
  return (
    <div className="mt-6 flex items-center justify-between gap-4 rounded-lg bg-surface-muted px-5 py-4">
      <div>
        <p className="font-semibold">Your share</p>
        <p className="text-ink-soft">{pickup.cost ? pickup.cost.explanation : "The price can't be worked out right now."}</p>
      </div>
      {pickup.cost && <p className="text-3xl font-extrabold">{formatMoney(pickup.cost.amountCents)}</p>}
    </div>
  );
}

/** Errors after which the trip can't be requested: the way forward is another trip. */
const LEAVE_CODES = new Set(["trip_full", "trip_not_open", "trip_not_found"]);

function RequestArea({
  tripId,
  state,
  vehicle,
  pickup,
  rider,
  request,
  onSent,
  name,
  back,
}: {
  tripId: string;
  state: "open" | "full";
  vehicle: Detail["vehicle"];
  pickup: PickupOption;
  rider: { lat: number; lng: number } | undefined;
  request: SeatRequest | undefined;
  onSent: (request: SeatRequest) => void;
  name: string | undefined;
  back: Back;
}) {
  const send = useRequestSeat(tripId, onSent);
  const cancel = useCancelSeatRequest(tripId);
  const [confirming, setConfirming] = useState(false);
  const driver = name ?? "The driver";
  const cancelError = cancel.error && (
    <p role="alert" className="text-sm font-semibold">
      {cancelRequestError(cancel.error.code)}
    </p>
  );

  if (request?.status === "accepted") {
    return (
      <div className="mt-8 space-y-3">
        <Notice title="You're in" tone="success">
          Be at {request.pickup.label} a few minutes early.
          {vehicle ? ` Look for a ${vehicle.colour} ${vehicle.make} ${vehicle.model}, plate ${vehicle.plate}.` : ""}
        </Notice>
        {confirming ? (
          <div role="group" aria-label="Cancel your seat?" className="space-y-3 rounded-lg border-2 border-line p-4">
            <p className="font-semibold">Cancel your seat? {driver} will be told, and the seat goes back to other riders.</p>
            <div className="grid grid-cols-2 gap-3">
              <Button variant="secondary" size="md" onClick={() => setConfirming(false)}>
                Keep my seat
              </Button>
              <Button variant="dark" size="md" loading={cancel.isPending} onClick={() => cancel.mutate(request.id)}>
                Cancel seat
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" size="md" fullWidth onClick={() => setConfirming(true)}>
            Cancel my seat
          </Button>
        )}
        {cancelError}
      </div>
    );
  }

  if (request?.status === "pending") {
    return (
      <div className="mt-8 space-y-3">
        <Notice title="Request sent" tone="waiting">
          Waiting for {name ?? "the driver"} to accept. This page updates when they decide, and you&apos;re only charged if
          they accept.
        </Notice>
        <Button variant="secondary" size="md" fullWidth loading={cancel.isPending} onClick={() => cancel.mutate(request.id)}>
          Cancel request
        </Button>
        {cancelError}
      </div>
    );
  }

  const outcome = request ? requestOutcome(request, name) : undefined;
  const here = typeof window === "undefined" ? `/ride/trip/${tripId}` : `${window.location.pathname}${window.location.search}`;
  const error = send.error ? requestSeatError(send.error.code, here) : undefined;
  const errorLink = error?.link ?? (send.error && LEAVE_CODES.has(send.error.code) ? back : undefined);

  return (
    <div className="mt-8 space-y-4">
      {outcome && (
        <Notice title={outcome.title} link={outcome.link} tone={request?.status === "cancelled" ? "neutral" : "ended"}>
          {outcome.text}
        </Notice>
      )}
      {error && (
        <div role="alert" className="rounded-lg border-2 border-ink px-5 py-4">
          <p className="font-bold">{error.title}</p>
          <p className="text-ink-soft">{error.text}</p>
          {errorLink && (
            <Link href={errorLink.href} className="mt-2 inline-block font-bold underline underline-offset-4">
              {errorLink.label}
            </Link>
          )}
        </div>
      )}
      {state === "full" ? (
        !error && <Notice title="No seats left">{driver}&apos;s trip is full. Go back to see other trips.</Notice>
      ) : (
        rider && (
          <>
            <Button fullWidth loading={send.isPending} onClick={() => send.mutate({ ...rider, pickupId: pickup.id })}>
              Request seat{pickup.cost ? ` · ${formatMoney(pickup.cost.amountCents)}` : ""}
            </Button>
            <PrivacyNote>
              {driver} will see this pickup point, never your address. You&apos;re only charged if{" "}
              {name ? `${name} accepts` : "they accept"}.
            </PrivacyNote>
          </>
        )
      )}
    </div>
  );
}

function NoPickup({ hasSearch, back }: { hasSearch: boolean; back: Back }) {
  return (
    <div className="mt-6 space-y-4 text-ink-soft">
      <p className="font-semibold text-ink">
        {hasSearch ? "This trip no longer passes within walking distance of your area." : "Search from your area to see where you'd be picked up."}
      </p>
      <Link href={back.href} className={buttonStyles({ size: "md", fullWidth: true })}>
        {hasSearch ? back.label : "Search for a ride"}
      </Link>
    </div>
  );
}

/**
 * How a request's state looks, so a change (e.g. waiting → accepted) is easy to notice:
 * success is green with a tick, waiting has a clock, ended (declined, expired, payment
 * failed) has a cross.
 */
const NOTICE_TONES = {
  success: { box: "border-brand bg-brand-tint", title: "text-brand", icon: CheckCircle2 },
  waiting: { box: "border-line bg-surface-muted", title: "", icon: Clock },
  ended: { box: "border-line-strong", title: "", icon: XCircle },
  neutral: { box: "border-line", title: "", icon: undefined },
} as const;

function Notice({
  title,
  children,
  link,
  tone = "neutral",
}: {
  title: string;
  children: ReactNode;
  link?: { href: string; label: string };
  tone?: keyof typeof NOTICE_TONES;
}) {
  const { box, title: titleClass, icon: Icon } = NOTICE_TONES[tone];
  return (
    <div role="status" className={cn("flex gap-3 rounded-lg border-2 px-5 py-4", box)}>
      {Icon && <Icon aria-hidden="true" className={cn("mt-0.5 size-6 shrink-0", tone === "success" ? "text-brand" : "text-ink")} />}
      <div className="min-w-0">
        <p className={cn("text-lg font-bold", titleClass)}>{title}</p>
        <p className="text-ink-soft">{children}</p>
        {link && (
          <Link href={link.href} className="mt-2 inline-block font-bold underline underline-offset-4">
            {link.label}
          </Link>
        )}
      </div>
    </div>
  );
}

function DetailError({ error, onRetry, back }: { error: ApiError | null; onRetry: () => void; back: Back }) {
  const code = error?.code;

  if (code === "unauthorized") {
    const next = typeof window === "undefined" ? "/ride" : `${window.location.pathname}${window.location.search}`;
    return (
      <Message title="Your session has ended">
        <p>Log in again to see this trip.</p>
        <Link href={`/login?next=${encodeURIComponent(next)}`} className={buttonStyles({ size: "md", fullWidth: true })}>
          Log in
        </Link>
      </Message>
    );
  }

  if (code === "trip_not_found" || code === "invalid_input") {
    return (
      <Message title="This trip is no longer available">
        <p>The driver may have removed it. Look for another trip at a similar time.</p>
        <Link href={back.href} className={buttonStyles({ size: "md", fullWidth: true })}>
          {back.label}
        </Link>
      </Message>
    );
  }

  const unavailable = code === "routing_unavailable" || code === "service_unavailable";
  return (
    <Message title={unavailable ? "Pickup points are unavailable right now" : "We couldn't load this trip"}>
      <p>{unavailable ? "We can't work out where you'd be picked up at the moment. Try again in a minute." : error?.message}</p>
      <div className="flex gap-3">
        <Button size="md" fullWidth onClick={onRetry}>
          Try again
        </Button>
        <Link href={back.href} className={buttonStyles({ variant: "secondary", size: "md", fullWidth: true })}>
          {back.label}
        </Link>
      </div>
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
