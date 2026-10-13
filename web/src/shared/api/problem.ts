import type { components } from "./generated/accounts";

/** Every error response from the backend (RFC 9457 Problem Details). See contracts/README.md. */
export type Problem = components["schemas"]["Problem"];

/** Thrown when an API call fails. `problem.code` is the stable name to check, e.g. "email_taken". */
export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.problem = problem;
  }

  get status(): number {
    return this.problem.status;
  }

  get code(): string {
    return this.problem.code;
  }
}

function isProblem(body: unknown): body is Problem {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as Problem).code === "string" &&
    typeof (body as Problem).status === "number"
  );
}

/**
 * Turns any failed response into a Problem. Responses that aren't Problem Details
 * (e.g. a 502 page from the gateway while a service restarts) get a generic one.
 */
export function toProblem(response: Response, body: unknown): Problem {
  if (isProblem(body)) {
    return body;
  }
  const unavailable = response.status === 502 || response.status === 503;
  return {
    type: "about:blank",
    title: response.statusText || "Error",
    status: response.status,
    detail: unavailable
      ? "The service is unavailable. Please try again in a moment."
      : "Something went wrong. Please try again.",
    instance: new URL(response.url || "http://unknown/").pathname,
    code: unavailable ? "service_unavailable" : "unexpected_error",
  };
}

/**
 * Returns the data of an openapi-fetch result, or throws an ApiError.
 *
 *   const user = await unwrap(accountsApi.GET("/me"));
 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) {
    throw new ApiError(toProblem(response, error));
  }
  return data as T;
}
