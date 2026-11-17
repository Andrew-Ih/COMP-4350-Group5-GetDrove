import { expect, test } from "@playwright/test";

import { nextWeekdayMorning } from "./winnipeg-time";

// No browser: these only check the search time the smoke test uses (8 AM is 13:00 UTC,
// since Winnipeg is UTC-5 all year from 2026).
test.describe("nextWeekdayMorning: 8 AM in Winnipeg on the next weekday", () => {
  test("is 13:00 UTC the next morning", () => {
    // Mon Nov 16 2026, noon in Winnipeg
    expect(nextWeekdayMorning(new Date("2026-11-16T17:00:00Z"))).toBe("2026-11-17T13:00:00.000Z");
  });

  test("stays 13:00 UTC after Nov 1, when clocks used to go back", () => {
    // Fri Oct 30 2026, noon in Winnipeg: Monday Nov 2 is still UTC-5
    expect(nextWeekdayMorning(new Date("2026-10-30T17:00:00Z"))).toBe("2026-11-02T13:00:00.000Z");
  });

  test("uses Winnipeg's date, not UTC's, late in the evening", () => {
    // Thu Nov 19 2026, 11:30 PM in Winnipeg, already Friday in UTC: the next weekday is Friday
    expect(nextWeekdayMorning(new Date("2026-11-20T04:30:00Z"))).toBe("2026-11-20T13:00:00.000Z");
  });

  test("skips the weekend", () => {
    // Fri Nov 20 2026, 1 PM in Winnipeg: next is Monday
    expect(nextWeekdayMorning(new Date("2026-11-20T18:00:00Z"))).toBe("2026-11-23T13:00:00.000Z");
  });

  test("from Saturday night it is Monday", () => {
    // Sat Nov 21 2026, 10 PM in Winnipeg (Sunday in UTC)
    expect(nextWeekdayMorning(new Date("2026-11-22T03:00:00Z"))).toBe("2026-11-23T13:00:00.000Z");
  });
});
