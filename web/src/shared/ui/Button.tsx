import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

import { Spinner } from "./Spinner";

const variants = {
  /** Main action of a screen: Find rides, Post trip, Accept. */
  primary: "bg-brand text-white hover:bg-brand-hover",
  /** Strong secondary action: Trip chat, selected options. */
  dark: "bg-ink text-white hover:bg-ink-soft",
  /** Outlined: Share trip, Statement. */
  outline: "border-2 border-ink bg-surface text-ink hover:bg-surface-muted",
  /** Quiet secondary: Decline. */
  secondary: "border-2 border-line-strong bg-surface text-ink hover:bg-surface-muted",
  /** Grey fill, e.g. round back and close buttons. */
  soft: "bg-surface-muted text-ink hover:bg-line",
} as const;

const sizes = {
  sm: "h-10 px-4 text-sm gap-1.5",
  md: "h-12 px-5 text-base gap-2",
  lg: "h-14 px-6 text-lg gap-2",
} as const;

type ButtonStyle = {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  fullWidth?: boolean;
};

/**
 * The button classes on their own, for links that should look like buttons:
 *
 *   <Link href="/login" className={buttonStyles({ fullWidth: true })}>Log in</Link>
 */
export function buttonStyles({ variant = "primary", size = "lg", fullWidth = false }: ButtonStyle = {}) {
  return cn(
    "inline-flex items-center justify-center rounded-md font-bold transition-colors",
    "disabled:cursor-not-allowed disabled:border-transparent disabled:bg-line disabled:text-subtle",
    variants[variant],
    sizes[size],
    fullWidth && "w-full",
  );
}

export type ButtonProps = ComponentProps<"button"> &
  ButtonStyle & {
    /** Shows a spinner and disables the button while an action runs. */
    loading?: boolean;
    /** Icon shown before the text. */
    icon?: ReactNode;
  };

export function Button({
  variant = "primary",
  size = "lg",
  fullWidth = false,
  loading = false,
  icon,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonStyles({ variant, size, fullWidth }), className)}
      {...props}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}
