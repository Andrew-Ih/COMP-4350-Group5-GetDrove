/**
 * Winnipeg is UTC-5 all year: Manitoba moved its clocks forward on Mar 8 2026 and stopped
 * changing them (https://gov.mb.ca/timechange). The offset is fixed here on purpose rather
 * than read from `America/Winnipeg`: Node bundles its own time zone data, and older Node
 * builds still expect clocks to go back on Nov 1, which would put the search at 9 AM.
 * The backend reads the zone from the pinned `tzdata` package (2026.5), which has the change.
 */
const WINNIPEG_OFFSET_HOURS = -5;

/** 8 AM in Winnipeg on the next weekday after today (in Winnipeg), as an ISO time. */
export function nextWeekdayMorning(now = new Date()): string {
  const local = new Date(now.getTime() + WINNIPEG_OFFSET_HOURS * 3600_000);
  const day = new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() + 1, 8 - WINNIPEG_OFFSET_HOURS));
  while (day.getUTCDay() === 0 || day.getUTCDay() === 6) day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString();
}
