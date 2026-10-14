import { cn } from "@/shared/lib/cn";

/** The GetDrove wordmark with its green square. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-baseline text-2xl font-extrabold tracking-tight", className)}>
      GetDrove
      <span aria-hidden="true" className="ml-0.5 inline-block size-[0.3em] rounded-[1px] bg-brand" />
    </span>
  );
}
