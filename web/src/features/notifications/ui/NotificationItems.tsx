"use client";

import { useRouter } from "next/navigation";

import { cn } from "@/shared/lib/cn";

import { useMarkRead } from "../hooks/useNotifications";
import { type Notification, notificationHref, timeAgo } from "../model/notifications";

/**
 * A list of notifications, unread ones marked with a dot. Choosing one marks it read and
 * goes to the trip (or page) it's about.
 */
export function NotificationItems({ items, onOpen }: { items: Notification[]; onOpen?: () => void }) {
  const router = useRouter();
  const markRead = useMarkRead();

  return (
    <ul className="divide-y divide-line">
      {items.map((n) => {
        const href = notificationHref(n);
        const unread = !n.readAt;
        return (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => {
                if (unread) markRead.mutate(n.id);
                onOpen?.();
                if (href) router.push(href);
              }}
              className={cn("flex w-full gap-3 px-4 py-3.5 text-left hover:bg-surface-muted", unread && "bg-brand-tint/60")}
            >
              <span
                aria-hidden="true"
                className={cn("mt-2 size-2.5 shrink-0 rounded-full", unread ? "bg-brand" : "bg-transparent")}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-3">
                  <span className={cn("truncate", unread ? "font-bold" : "font-semibold")}>{n.title}</span>
                  <span className="shrink-0 text-sm text-ink-soft">{timeAgo(n.createdAt)}</span>
                </span>
                <span className="mt-0.5 block text-ink-soft">{n.body}</span>
                {unread && <span className="sr-only">Unread</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
