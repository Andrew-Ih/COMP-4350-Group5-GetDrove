import { CarFront } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Logo, PrivacyNote } from "@/shared/ui";

import { AuthIllustration } from "./AuthIllustration";

/**
 * The frame of the signed-out pages (sign-up, verify, later log in), from the sign-up mockup.
 *
 * - Desktop: a white card on the left, the night illustration on the right.
 * - Mobile: the illustration at the top and the content sliding over it as a sheet.
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-surface md:grid md:grid-cols-[minmax(26rem,2fr)_3fr] md:bg-canvas">
      <div className="relative h-[26dvh] overflow-hidden md:order-2 md:h-auto">
        <AuthIllustration className="absolute inset-0 size-full" />
        <div className="absolute top-6 left-6 hidden items-center gap-3 rounded-lg bg-surface py-3 pr-5 pl-3 shadow-card lg:flex">
          <span className="flex size-10 items-center justify-center rounded-full bg-brand text-white">
            <CarFront aria-hidden="true" className="size-5" />
          </span>
          <span>
            <span className="block font-extrabold">Your ride to campus</span>
            <span className="block text-sm text-ink-soft">Arriving at University Centre · 8:12 AM</span>
          </span>
        </div>
      </div>

      <main className="relative z-10 -mt-6 flex flex-col rounded-t-xl bg-surface px-5 pt-6 pb-8 md:order-1 md:mt-0 md:items-center md:justify-center md:rounded-none md:bg-transparent md:px-8 md:py-6">
        <div className="w-full md:max-w-[28rem] md:rounded-xl md:bg-surface md:px-9 md:py-8 md:shadow-card">
          <Link href="/" aria-label="GetDrove home" className="inline-block">
            <Logo className="text-2xl" />
          </Link>
          <div className="mt-5">{children}</div>
        </div>
        <PrivacyNote className="mt-5 w-full md:max-w-[28rem]">
          Your home address is never shared. Riders meet drivers at pickup points.
        </PrivacyNote>
      </main>
    </div>
  );
}
