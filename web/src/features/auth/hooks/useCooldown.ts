"use client";

import { useCallback, useEffect, useState } from "react";

/** "0:45", "1:00": a number of seconds as minutes and seconds. */
export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * A countdown that starts on demand: `start()`, then `remaining` counts down to 0 once a
 * second. Used to stop a button being pressed again straight away.
 */
export function useCooldown(seconds: number) {
  const [until, setUntil] = useState<number>();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (until === undefined) return;
    const timer = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= until) setUntil(undefined);
    }, 1000);
    return () => clearInterval(timer);
  }, [until]);

  const start = useCallback(() => {
    const current = Date.now();
    setNow(current);
    setUntil(current + seconds * 1000);
  }, [seconds]);

  const remaining = until === undefined ? 0 : Math.max(0, Math.ceil((until - now) / 1000));
  return { remaining, start };
}
