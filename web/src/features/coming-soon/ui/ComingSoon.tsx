"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useCurrentUser } from "@/features/auth";
import { cn } from "@/shared/lib/cn";
import { AppHeader, buttonStyles, Card, Eyebrow } from "@/shared/ui";

/**
 * Stands in for a screen the header already links to but that lands in a later sprint
 * (#252), so the link doesn't lead to a 404. The real screen replaces the page that uses it.
 */
export function ComingSoon({
  title,
  description,
  icon,
  sprint,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  sprint: number;
}) {
  const me = useCurrentUser();

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="min-h-[calc(100dvh-4rem)] bg-canvas px-4 py-12 md:min-h-[calc(100dvh-4.5rem)]">
        <Card className="mx-auto max-w-md bg-surface p-8 text-center">
          <div aria-hidden="true" className="mx-auto flex size-14 items-center justify-center rounded-full bg-surface-muted">
            {icon}
          </div>
          <Eyebrow className="mt-6">Coming in Sprint {sprint}</Eyebrow>
          <h1 className="mt-2 text-3xl">{title}</h1>
          <p className="mt-3 text-lg text-ink-soft">{description}</p>
          <Link href="/ride" className={cn(buttonStyles({ fullWidth: true }), "mt-8")}>
            Find a ride
          </Link>
        </Card>
      </main>
    </>
  );
}
