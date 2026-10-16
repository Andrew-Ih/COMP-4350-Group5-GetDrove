"use client";

import { MailCheck } from "lucide-react";

import { Button } from "@/shared/ui";

import { useResendVerification } from "../hooks/useAuthMutations";

/** Shown after signing up: the verification email is on its way. */
export function CheckEmail({ email, onStartOver }: { email: string; onStartOver: () => void }) {
  const resend = useResendVerification();

  return (
    <div>
      <span className="flex size-12 items-center justify-center rounded-full bg-brand-tint text-brand">
        <MailCheck aria-hidden="true" className="size-7" />
      </span>
      <h1 className="mt-5 text-3xl leading-tight">Check your email</h1>
      <p className="mt-2 text-ink-soft">
        We sent a link to <strong className="text-ink">{email}</strong>. Open it within 24 hours to
        verify your account, then log in.
      </p>
      <p className="mt-3 text-ink-soft">Can&apos;t find it? Check your junk folder.</p>

      <div className="mt-6 flex flex-col gap-3">
        <Button
          variant="secondary"
          size="md"
          fullWidth
          loading={resend.isPending}
          disabled={resend.isSuccess}
          onClick={() => resend.mutate(email)}
        >
          {resend.isSuccess ? "New link sent" : "Send it again"}
        </Button>
        <p role="status" className="min-h-5 text-center text-sm text-ink-soft">
          {resend.isSuccess && "We sent a new link. Older links no longer work."}
          {resend.isError && "We couldn't send it right now. Try again in a moment."}
        </p>
        <button type="button" onClick={onStartOver} className="text-sm font-bold underline underline-offset-4">
          Wrong email? Start again
        </button>
      </div>
    </div>
  );
}
