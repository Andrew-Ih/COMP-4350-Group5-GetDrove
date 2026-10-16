"use client";

import { Button, type ButtonProps } from "@/shared/ui";

import { formatCountdown } from "../hooks/useCooldown";
import { useResend } from "../hooks/useResend";

/**
 * "Send a new link" for a known email, with the confirmation underneath. After sending,
 * the button counts down for a minute before it can be pressed again.
 */
export function ResendButton({
  email,
  label = "Send a new link",
  ...buttonProps
}: { email: string; label?: string } & Pick<ButtonProps, "variant" | "size" | "fullWidth" | "className">) {
  const resend = useResend();

  return (
    <div className="flex flex-col gap-2">
      <Button
        {...buttonProps}
        loading={resend.isPending}
        disabled={resend.secondsLeft > 0}
        onClick={() => resend.send(email)}
      >
        {resend.secondsLeft > 0 ? `Send again in ${formatCountdown(resend.secondsLeft)}` : label}
      </Button>
      <p role="status" className="text-sm">
        {resend.hasSent && !resend.isError && (
          <span className="font-semibold text-brand">We sent a new link. Older links no longer work.</span>
        )}
        {resend.isError && (
          <span className="font-semibold text-danger">We couldn&apos;t send it right now. Try again in a moment.</span>
        )}
      </p>
    </div>
  );
}
