import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/cn";

const variants = {
  /** LIVE, TRIP COMPLETE: green tint, uppercase. */
  status: "bg-brand-tint text-brand uppercase tracking-wider",
  /** Pending: green outline. */
  outline: "border-2 border-brand text-brand",
  /** Settled, 3 MIN: solid green. */
  solid: "bg-brand text-white",
  /** +3 min, 3 min on the map: black. */
  dark: "bg-ink text-white",
  /** Calculating…: grey. */
  neutral: "bg-surface-muted text-ink",
} as const;

export type BadgeProps = ComponentProps<"span"> & {
  variant?: keyof typeof variants;
  /** Adds a leading dot, e.g. for LIVE. */
  dot?: boolean;
};

export function Badge({ variant = "neutral", dot = false, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold whitespace-nowrap",
        variants[variant],
        className,
      )}
      {...props}
    >
      {dot && <span aria-hidden="true" className="size-2.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
