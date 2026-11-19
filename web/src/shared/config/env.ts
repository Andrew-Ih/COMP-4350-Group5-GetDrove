/**
 * Base URL of the backend APIs. Every service is under `<apiBaseUrl>/<service>`.
 *
 * The browser talks to one origin: Traefik sends /api/* to the services and everything
 * else to Next.js, so the relative default works locally, in Docker and on the live server.
 */
export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

/**
 * Stripe's publishable test key (pk_test_…), for the card form (#152). It's the public half
 * of the keys, meant for the browser; the secret key only lives in the Payments service.
 * Empty when it isn't configured: the Add card screen says so instead of showing the form.
 */
export const stripePublishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "";

/** Whether the mock API is on (NEXT_PUBLIC_API_MOCKING=enabled, e.g. `npm run dev:mock`). */
export const apiMocking = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
