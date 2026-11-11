// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { paths as NotificationsPaths } from "@/shared/api/generated/notifications";
import { unwrap } from "@/shared/api/problem";

import { resetNotifications } from "./notifications";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const notifications = createClient<NotificationsPaths>({ baseUrl: "http://localhost/api/notifications", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
  resetNotifications();
});
afterAll(() => server.close());

const list = (limit = 30) => unwrap(notifications.GET("/", { params: { query: { limit } } }));

describe("mock API: notifications", () => {
  it("lists them newest first with the unread count, up to the limit", async () => {
    const all = await list();
    expect(all.unreadCount).toBe(2);
    const created = all.items.map((n) => Date.parse(n.createdAt));
    expect(created).toEqual([...created].sort((a, b) => b - a));
    expect((await list(2)).items).toHaveLength(2);
  });

  it("marks one, then all, as read", async () => {
    const [first] = (await list()).items;
    await unwrap(notifications.POST("/{notification_id}/read", { params: { path: { notification_id: first!.id } } }));
    expect((await list()).unreadCount).toBe(1);
    await unwrap(notifications.POST("/read-all"));
    expect((await list()).unreadCount).toBe(0);
  });

  it("gets a new one about 30 seconds in", async () => {
    vi.useFakeTimers({ now: Date.now(), toFake: ["Date"] });
    resetNotifications();
    vi.setSystemTime(Date.now() + 31_000);
    const after = await list();
    expect(after.unreadCount).toBe(3);
    expect(after.items[0]!.title).toBe("New seat request");
  });
});
