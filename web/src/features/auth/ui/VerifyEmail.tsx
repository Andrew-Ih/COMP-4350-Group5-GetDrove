"use client";

import { CircleCheck, Clock, Link2Off } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useRef } from "react";

import { buttonStyles, Spinner } from "@/shared/ui";

import { useVerifyEmail } from "../hooks/useAuthMutations";
import { FormAlert } from "./FormAlert";
import { ResendForm } from "./ResendForm";

function Heading({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div>
      {icon}
      <h1 className="mt-5 text-3xl leading-tight">{title}</h1>
      <div className="mt-2 text-ink-soft">{children}</div>
    </div>
  );
}

const iconClass = "flex size-12 items-center justify-center rounded-full";

/**
 * The page the verification email links to (/verify?token=…). Sends the token once and
 * shows the result: verified, expired (with a form for a new link), or not valid.
 */
export function VerifyEmail({ token }: { token: string | undefined }) {
  const verify = useVerifyEmail();
  const sent = useRef(false);

  useEffect(() => {
    // Only once: a token works one time, so a second request would report "already used".
    // (React runs effects twice in development.)
    if (token && !sent.current) {
      sent.current = true;
      verify.mutate(token);
    }
  }, [token, verify]);

  if (!token) {
    return (
      <>
        <Heading
          icon={<span className={`${iconClass} bg-surface-muted`}><Link2Off aria-hidden="true" className="size-6" /></span>}
          title="This link is incomplete"
        >
          Open the link from your verification email again, or ask for a new one.
        </Heading>
        <div className="mt-6"><ResendForm /></div>
      </>
    );
  }

  if (verify.isSuccess) {
    return (
      <>
        <Heading
          icon={<span className={`${iconClass} bg-brand-tint text-brand`}><CircleCheck aria-hidden="true" className="size-6" /></span>}
          title="You're verified"
        >
          Your UofM email is confirmed. Log in to find or offer a ride.
        </Heading>
        <Link href="/login" className={`${buttonStyles({ size: "md", fullWidth: true })} mt-6`}>
          Log in
        </Link>
      </>
    );
  }

  if (verify.isError) {
    if (verify.error.code === "token_expired") {
      return (
        <>
          <Heading
            icon={<span className={`${iconClass} bg-surface-muted`}><Clock aria-hidden="true" className="size-6" /></span>}
            title="This link has expired"
          >
            Verification links last 24 hours. Enter your UofM email and we&apos;ll send a new one.
          </Heading>
          <div className="mt-6"><ResendForm /></div>
        </>
      );
    }
    if (verify.error.code === "invalid_token") {
      return (
        <>
          <Heading
            icon={<span className={`${iconClass} bg-surface-muted`}><Link2Off aria-hidden="true" className="size-6" /></span>}
            title="This link doesn't work"
          >
            It may have been used already, or replaced by a newer link. If you&apos;ve already verified,
            just log in.
          </Heading>
          <Link href="/login" className={`${buttonStyles({ size: "md", fullWidth: true })} mt-6`}>
            Log in
          </Link>
          <p className="mt-6 mb-4 font-bold">Still need to verify?</p>
          <ResendForm />
        </>
      );
    }
    return (
      <>
        <Heading
          icon={<span className={`${iconClass} bg-surface-muted`}><Link2Off aria-hidden="true" className="size-6" /></span>}
          title="We couldn't verify your email"
        >
          Something went wrong on our side.
        </Heading>
        <div className="mt-6"><FormAlert>{verify.error.problem.detail}</FormAlert></div>
        <button
          type="button"
          onClick={() => verify.mutate(token)}
          className={`${buttonStyles({ variant: "secondary", size: "md", fullWidth: true })} mt-6`}
        >
          Try again
        </button>
      </>
    );
  }

  return (
    <div role="status" className="flex items-center gap-3 py-10 text-lg text-ink-soft">
      <Spinner className="size-5" /> Verifying your email…
    </div>
  );
}
