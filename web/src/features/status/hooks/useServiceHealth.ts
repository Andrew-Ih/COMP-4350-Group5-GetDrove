"use client";

import { useEffect, useState } from "react";

import { checkHealth } from "../api/health";
import { type Health, SERVICES, type ServiceName } from "../model/services";

const REFRESH_MS = 15_000;

const initial = Object.fromEntries(SERVICES.map((s) => [s, "checking"])) as Record<
  ServiceName,
  Health
>;

/** Health of every service, refreshed every 15 seconds. */
export function useServiceHealth(): Record<ServiceName, Health> {
  const [health, setHealth] = useState(initial);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      const results = await Promise.all(SERVICES.map((s) => checkHealth(s)));
      if (!cancelled) {
        setHealth(
          Object.fromEntries(SERVICES.map((s, i) => [s, results[i] ?? "down"])) as typeof initial,
        );
      }
    }

    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return health;
}
