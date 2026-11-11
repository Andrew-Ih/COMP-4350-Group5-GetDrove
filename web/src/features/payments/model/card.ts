import type { components } from "@/shared/api/generated/payments";

export type PaymentMethod = components["schemas"]["PaymentMethod"];

/** An error from Stripe when confirming the card (its code, decline code and message). */
export type CardError = { code?: string; declineCode?: string; message?: string };

/** "Visa", "Mastercard"… from Stripe's brand name. */
export function brandName(brand: string): string {
  const names: Record<string, string> = {
    visa: "Visa",
    mastercard: "Mastercard",
    amex: "American Express",
    discover: "Discover",
    unionpay: "UnionPay",
    jcb: "JCB",
    diners: "Diners Club",
  };
  return names[brand] ?? "Card";
}

/** "Visa ending in 4242". */
export function cardLabel(card: PaymentMethod): string {
  return `${brandName(card.brand)} ending in ${card.last4}`;
}

/** "Expires 12/30". */
export function cardExpiry(card: PaymentMethod): string {
  return `Expires ${String(card.expMonth).padStart(2, "0")}/${String(card.expYear).slice(-2)}`;
}

/** The card holds go on: the default one, or the first. */
export function defaultCard(cards: PaymentMethod[]): PaymentMethod | undefined {
  return cards.find((c) => c.isDefault) ?? cards[0];
}

/** What the student is told when Stripe refuses the card. */
export function cardErrorMessage(error: CardError): string {
  switch (error.code) {
    case "card_declined":
      return error.declineCode === "insufficient_funds"
        ? "Your card has insufficient funds. Try a different card."
        : "Your card was declined. Try a different card.";
    case "expired_card":
      return "This card has expired. Try a different card.";
    case "incorrect_cvc":
    case "invalid_cvc":
      return "The security code (CVC) is incorrect.";
    case "incorrect_number":
    case "invalid_number":
      return "The card number is incorrect.";
    case "processing_error":
      return "Your card couldn't be processed. Try again.";
    default:
      return error.message ?? "We couldn't save this card. Try again.";
  }
}

/**
 * Where to go back to after adding a card (`?next=`), only if it's a page on this site:
 * a path starting with one "/", so a link can't send the student somewhere else.
 */
export function safeNext(next: string | undefined): string | undefined {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : undefined;
}
