"use client";

import { MailCheck } from "lucide-react";

import { ResendButton } from "./ResendButton";

/** Shown after signing up: the verification email is on its way. */
export function CheckEmail({ email, onStartOver }: { email: string; onStartOver: () => void }) {
  return (
    <div>
      <span className="flex size-12 items-center justify-center rounded-full bg-brand-tint text-brand">
        <MailCheck aria-hidden="true" className="size-6" />
      </span>
      <h1 className="mt-5 text-3xl leading-tight">Check your email</h1>
      <p className="mt-2 text-ink-soft">
        We sent a link to <strong className="text-ink">{email}</strong>. Open it within 24 hours to
        verify your account, then log in.
      </p>
      <p className="mt-3 text-ink-soft">Can&apos;t find it? Check your junk folder.</p>

      <div className="mt-6 flex flex-col gap-3">
        <ResendButton email={email} label="Send it again" variant="secondary" size="md" fullWidth />
        <button type="button" onClick={onStartOver} className="text-sm font-bold underline underline-offset-4">
          Wrong email? Start again
        </button>
      </div>
    </div>
  );
}
