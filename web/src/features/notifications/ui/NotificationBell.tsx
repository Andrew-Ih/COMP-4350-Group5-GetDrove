"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/shared/lib/cn";
import { Spinner } from "@/shared/ui";

import { useMarkRead, useNotifications } from "../hooks/useNotifications";
import { unreadBadge } from "../model/notifications";
import { NotificationItems } from "./NotificationItems";

const PANEL_LIMIT = 8;

/**
 * The bell in the header (#147): the unread count, and a panel with the latest
 * notifications. The count is checked every 30 s, and every 5 s while the panel is open.
 */
export function NotificationBell() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const notifications = useNotifications(PANEL_LIMIT, open);
  const markRead = useMarkRead();
  const box = useRef<HTMLDivElement>(null);
  const count = notifications.data?.unreadCount ?? 0;
  const badge = unreadBadge(count);

  // Close when clicking elsewhere or pressing Escape.
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "relative block rounded-full p-2 transition-colors hover:bg-surface-muted hover:text-ink",
          open || pathname.startsWith("/notifications") ? "text-ink" : "text-muted",
        )}
      >
        <Bell aria-hidden="true" className="size-6" />
        {badge && (
          <span
            aria-hidden="true"
            className="absolute -top-0.5 -right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1 text-xs font-bold text-white"
          >
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute top-full right-0 z-40 mt-2 w-96 overflow-hidden rounded-md bg-surface shadow-card"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="font-bold">Notifications</p>
            {count > 0 && (
              <button type="button" onClick={() => markRead.mutate("all")} className="text-sm font-bold text-brand hover:underline">
                Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {notifications.status === "pending" && (
              <p role="status" className="flex items-center gap-2 px-4 py-6 text-ink-soft">
                <Spinner className="size-4" /> Loading…
              </p>
            )}
            {notifications.status === "error" && (
              <p role="alert" className="px-4 py-6 text-ink-soft">
                We couldn&apos;t load your notifications.{" "}
                <button type="button" onClick={() => void notifications.refetch()} className="font-bold text-ink underline">
                  Try again
                </button>
              </p>
            )}
            {notifications.status === "success" &&
              (notifications.data.items.length === 0 ? (
                <p className="px-4 py-6 text-ink-soft">No notifications yet. Requests and trip updates will show up here.</p>
              ) : (
                <NotificationItems items={notifications.data.items} onOpen={() => setOpen(false)} />
              ))}
          </div>
          <Link
            href="/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-line px-4 py-3 text-center font-bold hover:bg-surface-muted"
          >
            See all
          </Link>
        </div>
      )}
    </div>
  );
}
