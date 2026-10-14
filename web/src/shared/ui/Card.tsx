import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/cn";

const variants = {
  /** White with a light border: request cards, trip results, stat cards. */
  outlined: "border-2 border-line bg-surface",
  /** The selected item in a list. */
  selected: "border-2 border-ink bg-surface",
  /** Grey fill without a border: "Your share", form groups. */
  muted: "bg-surface-muted",
  /** Black with white text: trip summary, total earned. */
  dark: "bg-ink text-white",
  /** Dashed border: an item still being worked out ("Calculating…"). */
  pending: "border-2 border-dashed border-line-strong bg-surface",
} as const;

export type CardProps = ComponentProps<"div"> & { variant?: keyof typeof variants };

export function Card({ variant = "outlined", className, ...props }: CardProps) {
  return <div className={cn("rounded-lg p-5", variants[variant], className)} {...props} />;
}
