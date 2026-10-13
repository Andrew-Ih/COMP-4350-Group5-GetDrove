"use client";

import { useServiceHealth } from "../hooks/useServiceHealth";
import { SERVICES } from "../model/services";

const LABEL = { checking: "Checking…", up: "Up", down: "Down" } as const;

/** Shows whether each backend service answers through the gateway. */
export function ServiceStatus() {
  const health = useServiceHealth();

  return (
    <ul className="status-list" aria-label="Service status">
      {SERVICES.map((service) => (
        <li key={service} className="status-row">
          <span className="status-name">{service}</span>
          <span className={`status-badge status-${health[service]}`}>{LABEL[health[service]]}</span>
        </li>
      ))}
    </ul>
  );
}
