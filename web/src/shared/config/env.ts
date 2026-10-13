/**
 * Base URL of the backend APIs. Every service is under `<apiBaseUrl>/<service>`.
 *
 * The browser talks to one origin: Traefik sends /api/* to the services and everything
 * else to Next.js, so the relative default works locally, in Docker and on the live server.
 */
export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
