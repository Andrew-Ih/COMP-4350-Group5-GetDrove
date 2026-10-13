import { setupServer } from "msw/node";

import { handlers } from "./handlers";

/** The same fake API for tests running in Node. */
export const server = setupServer(...handlers);
