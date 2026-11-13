// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as PaymentsPaths } from "@/shared/api/generated/payments";
import { unwrap } from "@/shared/api/problem";

import { addMockCard, resetMockCards } from "./payments";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const payments = createClient<PaymentsPaths>({ baseUrl: "http://localhost/api/payments", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetMockCards();
});
afterAll(() => server.close());

describe("mock API: payment cards", () => {
  it("starts a card setup with a client secret for Stripe", async () => {
    expect((await unwrap(payments.POST("/setup-intent"))).clientSecret).toBeTruthy();
  });

  it("starts with no card, then lists added cards newest first, the newest being the default", async () => {
    expect(await unwrap(payments.GET("/methods"))).toEqual([]);
    addMockCard({ brand: "visa", last4: "4242" });
    addMockCard({ brand: "mastercard", last4: "4444" });
    const cards = await unwrap(payments.GET("/methods"));
    expect(cards.map((c) => [c.last4, c.isDefault])).toEqual([
      ["4444", true],
      ["4242", false],
    ]);
  });
});
