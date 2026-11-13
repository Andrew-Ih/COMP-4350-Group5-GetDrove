"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useCurrentUser } from "@/features/auth";
import { AppHeader, buttonStyles, Card, Spinner } from "@/shared/ui";

import { useDriverProfile } from "../hooks/useDriver";
import { DRIVER_HREF, statusMessage } from "../model/driver";

/**
 * Shows `children` (Post a trip) only to approved drivers (#12). Everyone else sees why
 * they can't post yet and a link to the driver page, instead of a form that would fail.
 * If the status can't be loaded, the form is shown: the API refuses unapproved drivers
 * anyway (403 driver_not_approved), and the form explains that.
 */
export function DriverGate({ children }: { children: ReactNode }) {
  const me = useCurrentUser();
  const profile = useDriverProfile();

  if (profile.status === "success" && profile.data.status !== "approved") {
    const { title, text } = statusMessage(profile.data);
    return (
      <>
        <AppHeader userName={me.data?.firstName ?? ""} />
        <main className="min-h-[calc(100dvh-4rem)] bg-canvas px-4 py-12 md:min-h-[calc(100dvh-4.5rem)]">
          <Card className="mx-auto max-w-md bg-surface p-8">
            <h1 className="text-3xl">Get approved to drive</h1>
            <p className="mt-3 text-lg text-ink-soft">
              Only approved drivers can post trips, so riders know who&apos;s driving them.
            </p>
            <div className="mt-6 rounded-md bg-surface-muted px-4 py-3">
              <p className="font-bold">{title}</p>
              <p className="text-ink-soft">{text}</p>
            </div>
            <Link href={DRIVER_HREF} className={`${buttonStyles({ fullWidth: true })} mt-6`}>
              {profile.data.status === "pending" ? "See your application" : "Apply to drive"}
            </Link>
          </Card>
        </main>
      </>
    );
  }

  if (profile.status === "pending") {
    return (
      <>
        <AppHeader userName={me.data?.firstName ?? ""} />
        <p role="status" className="mt-16 flex items-center justify-center gap-3 font-semibold text-ink-soft">
          <Spinner className="size-5" /> Loading…
        </p>
      </>
    );
  }

  return children;
}
