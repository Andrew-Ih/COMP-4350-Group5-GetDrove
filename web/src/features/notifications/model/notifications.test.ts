import { describe, expect, it } from "vitest";

import { markReadIn, type Notification, notificationHref, timeAgo, unreadBadge } from "./notifications";

const NOW = new Date("2026-10-15T12:00:00Z");

const note = (changes: Partial<Notification> = {}): Notification => ({
  id: "n1",
  type: "request_accepted",
  title: "Request accepted",
  body: "Priya accepted your request.",
  tripId: "t1",
  requestId: "r1",
  createdAt: "2026-10-15T11:55:00Z",
  readAt: null,
  ...changes,
});

describe("notificationHref", () => {
  it("takes a rider to the trip", () => {
    for (const type of ["request_accepted", "request_declined", "trip_cancelled", "trip_reminder", "payment_failed"] as const) {
      expect(notificationHref(note({ type }))).toBe("/ride/trip/t1");
    }
  });

  it("takes a driver to their trip's requests", () => {
    expect(notificationHref(note({ type: "seat_requested" }))).toBe("/drive/trips/t1");
    expect(notificationHref(note({ type: "request_cancelled" }))).toBe("/drive/trips/t1");
  });

  it("takes driver approval news to the approval page", () => {
    expect(notificationHref(note({ type: "driver_approved", tripId: null }))).toBe("/account/driver");
    expect(notificationHref(note({ type: "driver_rejected", tripId: null }))).toBe("/account/driver");
  });

  it("goes nowhere without a trip", () => {
    expect(notificationHref(note({ tripId: null }))).toBeUndefined();
  });
});

describe("timeAgo", () => {
  it("says how long ago, then the date", () => {
    expect(timeAgo("2026-10-15T11:59:40Z", NOW)).toBe("just now");
    expect(timeAgo("2026-10-15T11:55:00Z", NOW)).toBe("5 min ago");
    expect(timeAgo("2026-10-15T09:00:00Z", NOW)).toBe("3 h ago");
    expect(timeAgo("2026-10-14T12:00:00Z", NOW)).toBe("1 day ago");
    expect(timeAgo("2026-10-12T12:00:00Z", NOW)).toBe("3 days ago");
    expect(timeAgo("2026-10-01T12:00:00Z", NOW)).toBe("Oct 1");
  });
});

describe("unreadBadge", () => {
  it("is hidden at 0 and caps at 9+", () => {
    expect(unreadBadge(0)).toBeUndefined();
    expect(unreadBadge(3)).toBe("3");
    expect(unreadBadge(12)).toBe("9+");
  });
});

describe("markReadIn", () => {
  const list = { items: [note(), note({ id: "n2" }), note({ id: "n3", readAt: "2026-10-15T10:00:00Z" })], unreadCount: 2 };

  it("marks one as read and lowers the count", () => {
    const next = markReadIn(list, "n1", "2026-10-15T12:00:00Z");
    expect(next.unreadCount).toBe(1);
    expect(next.items[0]!.readAt).toBe("2026-10-15T12:00:00Z");
  });

  it("leaves an already read one alone", () => {
    expect(markReadIn(list, "n3")).toBe(list);
  });

  it("marks all as read, keeping when the old ones were read", () => {
    const next = markReadIn(list, "all", "2026-10-15T12:00:00Z");
    expect(next.unreadCount).toBe(0);
    expect(next.items.map((n) => n.readAt)).toEqual(["2026-10-15T12:00:00Z", "2026-10-15T12:00:00Z", "2026-10-15T10:00:00Z"]);
  });
});
