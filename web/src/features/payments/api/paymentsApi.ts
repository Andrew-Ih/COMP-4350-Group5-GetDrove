import { paymentsApi, unwrap } from "@/shared/api";

/** POST /api/payments/setup-intent: starts adding a card; its clientSecret goes to Stripe. */
export function createSetupIntent() {
  return unwrap(paymentsApi.POST("/setup-intent"));
}

/** GET /api/payments/methods: the student's saved cards (brand, last 4, expiry), read from Stripe. */
export function getPaymentMethods() {
  return unwrap(paymentsApi.GET("/methods"));
}
