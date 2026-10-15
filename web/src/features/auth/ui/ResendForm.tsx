"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button, TextField } from "@/shared/ui";

import { useResendVerification } from "../hooks/useAuthMutations";
import { resendSchema, type ResendValues } from "../model/signup";

/** Ask for a new verification link. The answer is the same whether or not the account exists. */
export function ResendForm() {
  const resend = useResendVerification();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResendValues>({ resolver: zodResolver(resendSchema), defaultValues: { email: "" } });

  if (resend.isSuccess) {
    return (
      <p role="status" className="rounded-md bg-brand-tint p-4 font-semibold text-brand">
        If there&apos;s an unverified account for that email, a new link is on its way.
      </p>
    );
  }

  return (
    <form
      onSubmit={handleSubmit(({ email }) => resend.mutate(email))}
      noValidate
      className="flex flex-col gap-4"
    >
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
      <Button type="submit" size="md" fullWidth loading={resend.isPending}>
        Send a new link
      </Button>
    </form>
  );
}
