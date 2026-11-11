"use client";

import { ArrowLeft, Footprints } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { CAMPUS, type LngLat, type MapMarker, type MapRoute, MapView } from "@/shared/map";
import { AppHeader, Avatar, Button, buttonStyles, Eyebrow, MapLayout, PrivacyNote, Spinner } from "@/shared/ui";

import { useProfile, useRoute, useTripDetail } from "../hooks/useTripDetail";
import { formatClock, formatMoney, formatWalk, routeCoordinates } from "../model/results";
import { AREA_RADIUS_METERS, type SearchQuery, toQueryString } from "../model/search";
import {
  availability,
  type DriverProfile,
  driverLine,
  type PickupOption,
  seatsAndDeparture,
  type TripDetail as Detail,
} from "../model/tripDetail";

/**
 * A trip opened from the results (#140): the driver, the pickup point and the rider's
 * share, from GET /api/trips/{id}?lat&lng. The rider can pick another of the (up to 3)
 * pickup points (#136). `search` is the search the rider came from: its location is used
 * to find pickup points, and "All trips" goes back to its results. Without it, the trip
 * shows without pickup points.
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
  // Once the rider has asked for a seat, their request's pickup point and price are the ones that count.
  const request = detail.data?.myRequest;
  const pickup = useMemo<PickupOption | undefined>(
    () => (request ? { ...request.pickup, id: "my-request", cost: request.cost } : (pickups.find((p) => p.id === chosenId) ?? pickups[0])),
    [request, pickups, chosenId],
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
    for (const option of request ? [] : pickups) {
      if (option.id !== pickup?.id) list.push({ id: `option-${option.id}`, lngLat: [option.lng, option.lat], kind: "stop" });
    }
    if (pickup) list.push({ id: "pickup", lngLat: [pickup.lng, pickup.lat], kind: "pickup", label: pickup.label });
    if (you) list.push({ id: "you", lngLat: you, kind: "you", label: "You" });
    return list;
  }, [campus, request, pickups, pickup, you]);

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
                detail={detail.data}
                profile={profile.data}
                pickup={pickup}
                onChoosePickup={setChosenId}
                hasSearch={Boolean(search)}
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
  detail,
  profile,
  pickup,
  onChoosePickup,
  hasSearch,
  back,
}: {
  detail: Detail;
  profile: DriverProfile | undefined;
  pickup: PickupOption | undefined;
  onChoosePickup: (id: string) => void;
  hasSearch: boolean;
  back: Back;
}) {
  const { trip, vehicle, pickups, myRequest } = detail;
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
      canChoose={pickups.length > 1 && !myRequest}
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
          <RequestArea state={state} detail={detail} pickup={pickup} name={name} />
        </>
      ) : (
        <NoPickup hasSearch={hasSearch} back={back} />
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

function RequestArea({
  state,
  detail,
  pickup,
  name,
}: {
  state: "open" | "full";
  detail: Detail;
  pickup: PickupOption;
  name: string | undefined;
}) {
  const driver = name ?? "The driver";
  const request = detail.myRequest;

  if (request?.status === "accepted") {
    return (
      <Notice title="You're in">
        Be at {request.pickup.label} a few minutes early.
        {detail.vehicle
          ? ` Look for a ${detail.vehicle.colour} ${detail.vehicle.make} ${detail.vehicle.model}, plate ${detail.vehicle.plate}.`
          : ""}
      </Notice>
    );
  }
  if (request?.status === "pending") {
    return <Notice title="Request sent">Waiting for {name ?? "the driver"} to accept. You&apos;re only charged if they do.</Notice>;
  }
  if (state === "full") {
    return <Notice title="No seats left">{driver}&apos;s trip is full. Go back to see other trips.</Notice>;
  }

  return (
    <div className="mt-8 space-y-4">
      {/* Sending the request is #141; until then the button shows what it will do. */}
      <Button fullWidth disabled aria-describedby="request-soon">
        Request seat{pickup.cost ? ` · ${formatMoney(pickup.cost.amountCents)}` : ""}
      </Button>
      <p id="request-soon" className="text-sm text-ink-soft">
        Requesting a seat is coming soon.
      </p>
      <PrivacyNote>
        {driver} will see this pickup point, never your address. You&apos;re only charged if{" "}
        {name ? `${name} accepts` : "they accept"}.
      </PrivacyNote>
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

function Notice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div role="status" className="mt-8 rounded-lg border-2 border-line px-5 py-4">
      <p className="font-bold">{title}</p>
      <p className="text-ink-soft">{children}</p>
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
