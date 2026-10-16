"use client";

import { Eye, EyeOff } from "lucide-react";
import { type ComponentProps, useId, useState } from "react";

import { cn } from "@/shared/lib/cn";

export type TextFieldProps = Omit<ComponentProps<"input">, "id"> & {
  label: string;
  /** Help text under the field, e.g. "Only @myumanitoba.ca emails". */
  hint?: string;
  /** Error message; marks the field invalid for screen readers too. */
  error?: string;
  /** Shorter field for dense forms, e.g. sign-up on a laptop screen. */
  compact?: boolean;
};

/** Labelled text input. type="password" adds a show/hide button. */
export function TextField({
  label,
  hint,
  error,
  compact = false,
  type = "text",
  className,
  ...props
}: TextFieldProps) {
  const id = useId();
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";
  const describedBy = [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ");

  return (
    <div className={cn("flex flex-col", compact ? "gap-1.5" : "gap-2", className)}>
      <label htmlFor={id} className="text-sm font-bold text-ink">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={isPassword && revealed ? "text" : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={cn(
            "w-full rounded-md bg-surface-muted text-ink placeholder:text-subtle",
            compact ? "h-12 px-4 text-base" : "h-14 px-5 text-lg",
            "border-2 border-transparent focus:border-brand focus:outline-none",
            error && "border-danger",
            isPassword && (compact ? "pr-12" : "pr-14"),
          )}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed((r) => !r)}
            aria-label={revealed ? "Hide password" : "Show password"}
            className={cn(
              "absolute inset-y-0 right-0 flex items-center justify-center text-ink",
              compact ? "w-12" : "w-14",
            )}
          >
            {revealed ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
          </button>
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
