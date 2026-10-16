import type { Problem } from "@/shared/api";

/**
 * Turns a Problem Details response into messages per form field, plus a message for the
 * form as a whole when no field fits. Field names in `errors` are the contract's camelCase
 * names (e.g. "firstName"), sometimes with a path in front ("body.firstName").
 */
export function fieldErrorsFrom<Field extends string>(
  problem: Problem,
  fields: readonly Field[],
): { fields: Partial<Record<Field, string>>; form?: string } {
  const result: Partial<Record<Field, string>> = {};

  for (const error of problem.errors ?? []) {
    const name = error.field.split(".").pop() as Field;
    if (fields.includes(name)) {
      result[name] ??= error.message;
    }
  }

  const matched = Object.keys(result).length > 0;
  return matched ? { fields: result } : { fields: result, form: problem.detail };
}
