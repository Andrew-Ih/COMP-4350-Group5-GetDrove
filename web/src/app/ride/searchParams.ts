/** Next.js page `searchParams` as URLSearchParams. A repeated key keeps its first value. */
export function toSearchParams(params: Record<string, string | string[] | undefined>): URLSearchParams {
  const result = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const first = Array.isArray(value) ? value[0] : value;
    if (first !== undefined) result.set(key, first);
  }
  return result;
}
