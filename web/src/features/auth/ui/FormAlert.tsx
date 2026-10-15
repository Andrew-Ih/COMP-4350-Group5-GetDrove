import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";

/** A message about the whole form, e.g. when the service can't be reached. */
export function FormAlert({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md bg-danger-tint p-4 text-danger">
      <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="text-sm font-semibold">{children}</div>
    </div>
  );
}
