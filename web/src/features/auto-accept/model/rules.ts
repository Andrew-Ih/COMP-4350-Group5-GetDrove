import type { components } from "@/shared/api/generated/trips";

export type AutoAcceptRules = components["schemas"]["AutoAcceptRules"];

/** The contract's limits for the maximum detour, in minutes. */
export const MAX_DETOUR_MINUTES = 30;

/** The minimum ratings offered. `null` is "any rating". */
export const RATING_OPTIONS: readonly (number | null)[] = [null, 3, 3.5, 4, 4.5];

/** The rating options, with the driver's saved one added if it's not one of them (e.g. 4.2). */
export function ratingOptions(saved: number | null): (number | null)[] {
  const options = [...RATING_OPTIONS];
  if (saved !== null && !options.includes(saved)) options.push(saved);
  return options.sort((a, b) => (a ?? 0) - (b ?? 0));
}

/** "Any rating" or "4.0 or higher". */
export function ratingLabel(rating: number | null): string {
  return rating === null ? "Any rating" : `${rating.toFixed(1)} or higher`;
}

export type RulesForm = { enabled: boolean; maxDetourMinutes: string; minRating: number | null };

export type RulesProblem = { field: "maxDetourMinutes" | "minRating"; message: string };

/**
 * The rules to save from what the driver chose, or what to fix first. The same limits the
 * API checks. The values are kept (and checked) even with auto-accept off, so turning it
 * back on brings them back.
 */
export function buildRules(form: RulesForm): { rules: AutoAcceptRules } | { problem: RulesProblem } {
  const text = form.maxDetourMinutes.trim();
  const minutes = Number(text);
  if (text === "" || !Number.isInteger(minutes) || minutes < 0 || minutes > MAX_DETOUR_MINUTES) {
    return { problem: { field: "maxDetourMinutes", message: `Enter a whole number of minutes from 0 to ${MAX_DETOUR_MINUTES}.` } };
  }
  if (form.minRating !== null && (form.minRating < 1 || form.minRating > 5)) {
    return { problem: { field: "minRating", message: "Choose a rating from 1 to 5, or any rating." } };
  }
  return { rules: { enabled: form.enabled, maxDetourMinutes: minutes, minRating: form.minRating } };
}

/** What the rules do, in one sentence. */
export function rulesSummary(rules: AutoAcceptRules): string {
  if (!rules.enabled) return "Every request waits for you to accept or decline it.";
  const detour = rules.maxDetourMinutes === 0 ? "add no detour" : `add at most ${rules.maxDetourMinutes} min`;
  const riders = rules.minRating === null ? "from any rider" : `from riders rated ${rules.minRating.toFixed(1)} or higher (or new riders)`;
  return `Requests that ${detour}, ${riders}, are accepted for you while you have seats free.`;
}
