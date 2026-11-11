import { http, HttpResponse } from "msw";

import type { components as Notifications } from "@/shared/api/generated/notifications";

/**
 * Mock API for notifications (#147), matching the Notifications contract. It starts with
 * five notifications, two of them unread, and a new one arrives about 30 seconds after the
 * page loads, so the bell's count can be seen changing on its own.
 */

type Notification = Notifications["schemas"]["Notification"];

const ARRIVES_AFTER_MS = 30_000;

function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function note(id: number, type: Notification["type"], title: string, body: string, minutes: number, read: boolean, tripId?: string): Notification {
  return {
    id: `99999999-0000-4000-8000-${String(id).padStart(12, "0")}`,
    type,
    title,
    body,
    tripId: tripId ?? null,
    requestId: null,
    createdAt: minutesAgo(minutes),
    readAt: read ? minutesAgo(minutes - 1) : null,
  };
}

function initial(): Notification[] {
  return [
    note(1, "request_accepted", "Request accepted", "Priya accepted your request for tomorrow at 7:52 AM.", 4, false, "22222222-2222-4222-8222-222222222222"),
    note(2, "seat_requested", "New seat request", "Amara asked for a seat on your trip on Fri at 8:00 AM.", 50, false, "77777777-0000-4000-8000-000000000001"),
    note(3, "request_declined", "Request declined", "Daniel couldn't take you on Sat at 7:50 AM. Try another trip.", 60 * 5, true, "33333333-3333-4333-8333-333333333333"),
    note(4, "trip_cancelled", "Trip cancelled", "Amira cancelled the trip on Mon at 7:44 AM. You weren't charged.", 60 * 26, true, "11111111-1111-4111-8111-111111111111"),
    note(5, "driver_approved", "You're approved to drive", "Your licence and insurance were approved. You can post trips now.", 60 * 24 * 3, true),
  ];
}

let items = initial();
let startedAt = Date.now();
let arrived = false;

/** Starts again from the first five notifications (for tests). */
export function resetNotifications() {
  items = initial();
  startedAt = Date.now();
  arrived = false;
}

function list(limit: number) {
  if (!arrived && Date.now() - startedAt > ARRIVES_AFTER_MS) {
    arrived = true;
    items.unshift(
      note(6, "seat_requested", "New seat request", "Ethan asked for a seat on your trip on Fri at 8:00 AM.", 0, false, "77777777-0000-4000-8000-000000000001"),
    );
  }
  return { items: items.slice(0, limit), unreadCount: items.filter((n) => !n.readAt).length };
}

export const notificationHandlers = [
  http.get("*/api/notifications/", ({ request }) => {
    const limit = Number(new URL(request.url).searchParams.get("limit") ?? 30);
    return HttpResponse.json(list(limit));
  }),
  http.post("*/api/notifications/read-all", () => {
    const now = new Date().toISOString();
    for (const n of items) n.readAt ??= now;
    return new HttpResponse(null, { status: 204 });
  }),
  http.post("*/api/notifications/:notificationId/read", ({ params }) => {
    const found = items.find((n) => n.id === String(params.notificationId));
    if (!found) {
      return HttpResponse.json(
        { type: "about:blank", title: "Not found", status: 404, detail: "No notification with this ID", instance: "/api/notifications", code: "notification_not_found", requestId: "mock" },
        { status: 404, headers: { "Content-Type": "application/problem+json" } },
      );
    }
    found.readAt ??= new Date().toISOString();
    return new HttpResponse(null, { status: 204 });
  }),
];
