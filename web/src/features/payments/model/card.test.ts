import { describe, expect, it } from "vitest";

import { brandName, cardErrorMessage, cardExpiry, cardLabel, defaultCard, type PaymentMethod, safeNext } from "./card";

const visa: PaymentMethod = { id: "pm_1", brand: "visa", last4: "4242", expMonth: 3, expYear: 2030, isDefault: true };

describe("the saved card", () => {
  it("is described by brand, last 4 digits and expiry", () => {
    expect(cardLabel(visa)).toBe("Visa ending in 4242");
    expect(cardExpiry(visa)).toBe("Expires 03/30");
    expect(brandName("mastercard")).toBe("Mastercard");
    expect(brandName("something_new")).toBe("Card");
  });

  it("is the default card, or the first", () => {
    const other = { ...visa, id: "pm_2", isDefault: false };
    expect(defaultCard([other, visa])).toBe(visa);
    expect(defaultCard([other])).toBe(other);
    expect(defaultCard([])).toBeUndefined();
  });
});

describe("cardErrorMessage", () => {
  it("explains declined and invalid cards", () => {
    expect(cardErrorMessage({ code: "card_declined", declineCode: "generic_decline" })).toBe("Your card was declined. Try a different card.");
    expect(cardErrorMessage({ code: "card_declined", declineCode: "insufficient_funds" })).toMatch(/insufficient funds/);
    expect(cardErrorMessage({ code: "expired_card" })).toMatch(/expired/);
    expect(cardErrorMessage({ code: "incorrect_cvc" })).toMatch(/CVC/);
  });

  it("falls back to Stripe's own message, then a general one", () => {
    expect(cardErrorMessage({ code: "something_else", message: "Stripe says no." })).toBe("Stripe says no.");
    expect(cardErrorMessage({})).toBe("We couldn't save this card. Try again.");
  });
});

describe("safeNext", () => {
  it("allows a page on this site", () => {
    expect(safeNext("/ride/trip/t1?lat=1&lng=2")).toBe("/ride/trip/t1?lat=1&lng=2");
  });

  it("refuses anything that could leave the site", () => {
    expect(safeNext("https://example.com")).toBeUndefined();
    expect(safeNext("//example.com")).toBeUndefined();
    expect(safeNext(undefined)).toBeUndefined();
  });
});
