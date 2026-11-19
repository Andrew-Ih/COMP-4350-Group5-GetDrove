import { http, HttpResponse } from "msw";

import type { components as Payments } from "@/shared/api/generated/payments";

/**
 * Mock API for payment cards (#152), matching the Payments contract. There's no Stripe
 * account in mock mode: the stand-in card form (features/payments/ui/MockCardField) adds
 * the card here, the way Stripe would, and GET /api/payments/methods lists it. The student
 * starts with no card.
 */

type PaymentMethod = Payments["schemas"]["PaymentMethod"];

const cards: PaymentMethod[] = [];

/** What a successful stripe.confirmCardSetup does: the card is now on the student's account. */
export function addMockCard(card: { brand: string; last4: string }) {
  for (const c of cards) c.isDefault = false; // the newest card is the one holds go on
  cards.unshift({ id: `pm_mock_${cards.length + 1}`, brand: card.brand, last4: card.last4, expMonth: 12, expYear: 2030, isDefault: true });
}

/** Removes the saved cards (for tests). */
export function resetMockCards() {
  cards.length = 0;
}

export const paymentHandlers = [
  http.post("*/api/payments/setup-intent", () =>
    HttpResponse.json({ clientSecret: "seti_mock_secret" } satisfies Payments["schemas"]["SetupIntent"], { status: 201 }),
  ),
  http.get("*/api/payments/methods", () => HttpResponse.json(cards)),
];
