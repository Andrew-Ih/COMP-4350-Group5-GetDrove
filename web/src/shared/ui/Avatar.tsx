import { cn } from "@/shared/lib/cn";

const tones = {
  light: "bg-surface-muted text-ink",
  soft: "bg-brand-soft text-ink",
  dark: "bg-ink text-white",
  brand: "bg-brand text-white",
} as const;

const sizes = {
  sm: "size-8 text-sm",
  md: "size-12 text-lg",
  lg: "size-16 text-2xl",
} as const;

export type AvatarProps = {
  name: string;
  tone?: keyof typeof tones;
  size?: keyof typeof sizes;
  className?: string;
};

/** A person's first initial in a circle. */
export function Avatar({ name, tone = "light", size = "md", className }: AvatarProps) {
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-extrabold",
        tones[tone],
        sizes[size],
        className,
      )}
    >
      {name.trim().charAt(0).toUpperCase()}
    </span>
  );
}
