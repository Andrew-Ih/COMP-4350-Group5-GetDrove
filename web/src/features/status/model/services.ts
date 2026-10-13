export const SERVICES = ["accounts", "trips", "routing", "payments", "notifications"] as const;

export type ServiceName = (typeof SERVICES)[number];

export type Health = "checking" | "up" | "down";
