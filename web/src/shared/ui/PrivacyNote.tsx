import { Lock } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

/** The lock line at the bottom of most screens: "Riders never see where you start." */
export function PrivacyNote({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-start gap-2.5 text-sm text-ink-soft", className)}>
      <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink" />
      <span>{children}</span>
    </p>
  );
}
