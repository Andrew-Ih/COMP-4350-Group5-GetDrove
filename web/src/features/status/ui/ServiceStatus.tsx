"use client";

import { Badge } from "@/shared/ui";

import { useServiceHealth } from "../hooks/useServiceHealth";
import { type Health, SERVICES } from "../model/services";

const BADGE: Record<Health, { label: string; variant: "solid" | "dark" | "neutral" }> = {
  checking: { label: "Checking…", variant: "neutral" },
  up: { label: "Up", variant: "solid" },
  down: { label: "Down", variant: "dark" },
};

/** Shows whether each backend service answers through the gateway. */
export function ServiceStatus() {
  const health = useServiceHealth();

  return (
    <ul aria-label="Service status" className="divide-y divide-line">
      {SERVICES.map((service) => (
        <li key={service} className="flex items-center justify-between py-3">
          <span className="text-lg font-semibold capitalize">{service}</span>
          <Badge variant={BADGE[health[service]].variant}>{BADGE[health[service]].label}</Badge>
        </li>
      ))}
    </ul>
  );
}
