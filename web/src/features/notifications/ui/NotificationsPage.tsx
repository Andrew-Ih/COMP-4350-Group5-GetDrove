"use client";

import { useState } from "react";

import { useCurrentUser } from "@/features/auth";
import { AppHeader, Button, Spinner } from "@/shared/ui";

import { useMarkRead, useNotifications } from "../hooks/useNotifications";
import { NotificationItems } from "./NotificationItems";

/** The page shows the newest 50, then up to 100 with "Show more" (the most the API returns). */
const FIRST_PAGE = 50;
const MOST = 100;

/** /notifications (#147): the full list, where the bell leads on phones and from "See all". */
export function NotificationsPage() {
  const me = useCurrentUser();
  const [limit, setLimit] = useState(FIRST_PAGE);
  const notifications = useNotifications(limit, true);
  const shown = notifications.data?.items.length ?? 0;
  const markRead = useMarkRead();
  const count = notifications.data?.unreadCount ?? 0;

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-2xl px-5 py-8 md:py-12">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-3xl md:text-4xl">Notifications</h1>
          {count > 0 && (
            <Button variant="secondary" size="sm" onClick={() => markRead.mutate("all")}>
              Mark all as read
            </Button>
          )}
        </div>
        {count > 0 && <p className="mt-1 text-ink-soft">{count} unread</p>}

        <div className="mt-6 overflow-hidden rounded-lg border-2 border-line">
          {notifications.status === "pending" && (
            <p role="status" className="flex items-center gap-2 px-4 py-6 text-ink-soft">
              <Spinner className="size-4" /> Loading…
            </p>
          )}
          {notifications.status === "error" && (
            <div role="alert" className="space-y-3 px-4 py-6 text-ink-soft">
              <p>We couldn&apos;t load your notifications.</p>
              <Button size="sm" onClick={() => void notifications.refetch()}>
                Try again
              </Button>
            </div>
          )}
          {notifications.status === "success" &&
            (notifications.data.items.length === 0 ? (
              <p className="px-4 py-6 text-ink-soft">No notifications yet. Requests and trip updates will show up here.</p>
            ) : (
              <NotificationItems items={notifications.data.items} />
            ))}
        </div>

        {shown === limit && limit < MOST && (
          <Button variant="secondary" size="md" fullWidth className="mt-4" loading={notifications.isPlaceholderData} onClick={() => setLimit(MOST)}>
            Show more
          </Button>
        )}
        {shown === MOST && limit === MOST && <p className="mt-4 text-center text-sm text-ink-soft">Showing your latest {MOST} notifications.</p>}
      </main>
    </>
  );
}
