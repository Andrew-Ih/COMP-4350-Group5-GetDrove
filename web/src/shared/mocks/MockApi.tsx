"use client";

import { type ReactNode, useEffect, useState } from "react";

import { worker } from "./browser";

// Started once per page load. React runs effects twice in development (Strict Mode),
// and MSW refuses to start a second time.
let started: Promise<unknown> | undefined;
function startOnce() {
  started ??= worker.start({ onUnhandledFrame: "bypass", quiet: true });
  return started;
}

/**
 * Starts the mock API in the browser, then shows the page, so the first requests are
 * intercepted too. Only loaded when NEXT_PUBLIC_API_MOCKING=enabled (see app/providers.tsx).
 */
export function MockApi({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    void startOnce().then(() => setReady(true));
  }, []);

  return ready ? children : null;
}
