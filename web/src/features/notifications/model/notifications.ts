import type { components } from "@/shared/api/generated/notifications";

export type Notification = components["schemas"]["Notification"];
export type NotificationList = components["schemas"]["NotificationList"];

/** How often the unread count is checked: often while the panel is open, otherwise now and then. */
export const POLL_OPEN_MS = 5_000;
export const POLL_CLOSED_MS = 30_000;

/** Where the driver approval page is (#12). */
export const DRIVER_APPROVAL_HREF = "/account/driver";

/**
 * Where a notification takes the student: a driver to their trip's requests, a rider to the
 * trip, and driver approval news to the approval page. Undefined if there's nowhere to go.
 */
export function notificationHref(n: Notification): string | undefined {
  switch (n.type) {
    case "seat_requested":
    case "request_cancelled":
      return n.tripId ? `/drive/trips/${n.tripId}` : undefined;
    case "driver_approved":
    case "driver_rejected":
      return DRIVER_APPROVAL_HREF;
    default:
      return n.tripId ? `/ride/trip/${n.tripId}` : undefined;
  }
}

/** "just now", "5 min ago", "3 h ago", "2 days ago", then the date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.floor((now.getTime() - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} ${days === 1 ? "day" : "days"} ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** The badge on the bell: nothing at 0, "9+" above 9. */
export function unreadBadge(count: number): string | undefined {
  if (count <= 0) return undefined;
  return count > 9 ? "9+" : String(count);
}

/** The list after marking one (or all) as read, so the screen updates before it's fetched again. */
export function markReadIn(list: NotificationList, id: string | "all", at: string = new Date().toISOString()): NotificationList {
  if (id === "all") return { items: list.items.map((n) => ({ ...n, readAt: n.readAt ?? at })), unreadCount: 0 };
  const target = list.items.find((n) => n.id === id);
  if (!target || target.readAt) return list;
  return {
    items: list.items.map((n) => (n.id === id ? { ...n, readAt: at } : n)),
    unreadCount: Math.max(0, list.unreadCount - 1),
  };
}
