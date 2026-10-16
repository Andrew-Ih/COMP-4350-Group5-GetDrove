"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button, TextField } from "@/shared/ui";

import { formatCountdown } from "../hooks/useCooldown";
import { useResend } from "../hooks/useResend";
import { resendSchema, type ResendValues } from "../model/signup";

/**
 * Ask for a new verification link by email. The answer is the same whether or not the
 * account exists. After sending, the button counts down for a minute; the email can still
 * be corrected meanwhile.
 */
export function ResendForm() {
  const resend = useResend();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResendValues>({ resolver: zodResolver(resendSchema), defaultValues: { email: "" } });

  return (
    <form
      onSubmit={handleSubmit(({ email }) => resend.send(email))}
      noValidate
      className="flex flex-col gap-4"
    >
      {resend.hasSent && !resend.isError && (
        <p role="status" className="rounded-md bg-brand-tint p-4 font-semibold text-brand">
          If there&apos;s an unverified account for that email, a new link is on its way.
        </p>
      )}
      <TextField
        compact
        label="UofM email"
        type="email"
        autoComplete="email"
        placeholder="you@myumanitoba.ca"
        error={errors.email?.message}
        {...register("email")}
      />
      {resend.isError && (
        <p role="alert" className="text-sm font-semibold text-danger">
          We couldn&apos;t send it right now. Try again in a moment.
        </p>
      )}
      <Button
        type="submit"
        size="md"
        fullWidth
        loading={resend.isPending}
        disabled={resend.secondsLeft > 0}
      >
        {resend.secondsLeft > 0 ? `Send again in ${formatCountdown(resend.secondsLeft)}` : "Send a new link"}
      </Button>
    </form>
  );
}
