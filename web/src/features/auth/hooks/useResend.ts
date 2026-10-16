"use client";

import { useState } from "react";

import { useCooldown } from "./useCooldown";
import { useResendVerification } from "./useAuthMutations";

/** How long to wait before another verification email can be requested. */
export const RESEND_COOLDOWN_SECONDS = 60;

/**
 * Sends a new verification link, then waits a minute before allowing another, so nobody
 * floods their own inbox by pressing twice. (Real abuse protection is rate limiting on
 * the server; this is for honest users.)
 */
export function useResend() {
  const mutation = useResendVerification();
  const cooldown = useCooldown(RESEND_COOLDOWN_SECONDS);
  const [hasSent, setHasSent] = useState(false);

  function send(email: string) {
    mutation.mutate(email, {
      onSuccess: () => {
        setHasSent(true);
        cooldown.start();
      },
    });
  }

  return {
    send,
    isPending: mutation.isPending,
    isError: mutation.isError,
    hasSent,
    secondsLeft: cooldown.remaining,
  };
}
