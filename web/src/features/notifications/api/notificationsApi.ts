import { notificationsApi, unwrap } from "@/shared/api";

/** GET /api/notifications/?limit=: the latest notifications, newest first, and the unread count. */
export function getNotifications(limit: number) {
  return unwrap(notificationsApi.GET("/", { params: { query: { limit } } }));
}

/** POST /api/notifications/{id}/read */
export function markRead(notificationId: string) {
  return unwrap(notificationsApi.POST("/{notification_id}/read", { params: { path: { notification_id: notificationId } } }));
}

/** POST /api/notifications/read-all */
export function markAllRead() {
  return unwrap(notificationsApi.POST("/read-all"));
}
