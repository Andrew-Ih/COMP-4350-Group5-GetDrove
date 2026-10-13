import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

/** Intercepts API calls in the browser. Started by src/app/providers.tsx when mocking is on. */
export const worker = setupWorker(...handlers);
