"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getNotifications, markAllRead, markRead } from "../api/notificationsApi";
import { markReadIn, type NotificationList, POLL_CLOSED_MS, POLL_OPEN_MS } from "../model/notifications";

const KEY = ["notifications"] as const;

/**
 * The latest notifications and the unread count, checked every 30 s while the app is
 * open, or every 5 s with `watching` (the panel or page is open).
 */
export function useNotifications(limit: number, watching: boolean) {
  return useQuery<NotificationList, ApiError>({
    queryKey: [...KEY, limit],
    queryFn: () => getNotifications(limit),
    refetchInterval: watching ? POLL_OPEN_MS : POLL_CLOSED_MS,
    // Asking for more keeps the list on screen while the longer one loads.
    placeholderData: keepPreviousData,
  });
}

/** Marks one notification (or "all") as read; the badge and list change straight away. */
export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation<unknown, ApiError, string | "all">({
    mutationFn: (id) => (id === "all" ? markAllRead() : markRead(id)),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: KEY });
      queryClient.setQueriesData<NotificationList>({ queryKey: KEY }, (list) => list && markReadIn(list, id));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}
