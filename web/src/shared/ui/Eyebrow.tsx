import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/cn";

/** Small uppercase label above a value: "PICKUP · 7:48 AM", "DROP-OFF · 8:12 AM". */
export function Eyebrow({
  tone = "brand",
  className,
  ...props
}: ComponentProps<"p"> & { tone?: "brand" | "muted" }) {
  return (
    <p
      className={cn(
        "text-xs font-bold tracking-wider uppercase",
        tone === "brand" ? "text-brand" : "text-muted",
        className,
      )}
      {...props}
    />
  );
}
