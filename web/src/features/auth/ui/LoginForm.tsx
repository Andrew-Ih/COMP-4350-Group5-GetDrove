"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MailWarning } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button, TextField } from "@/shared/ui";

import { useLogin } from "../hooks/useAuthMutations";
import { loginSchema, type LoginValues, safeNext } from "../model/login";
import { fieldErrorsFrom } from "../model/serverErrors";
import { FormAlert } from "./FormAlert";
import { ResendButton } from "./ResendButton";

const FIELDS = ["email", "password"] as const;

/** Log in with a UofM email and password (#92). `next` is the page to return to. */
export function LoginForm({ next }: { next?: string }) {
  const router = useRouter();
  const login = useLogin();
  const [formError, setFormError] = useState<string>();
  const [unverifiedEmail, setUnverifiedEmail] = useState<string>();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined);
    setUnverifiedEmail(undefined);
    login.mutate(values, {
      onSuccess: () => router.push(safeNext(next)),
      onError: (error) => {
        if (error.code === "invalid_credentials") {
          // One message for both, so the form doesn't reveal which emails have accounts.
          setFormError("Wrong email or password.");
          return;
        }
        if (error.code === "email_not_verified") {
          setUnverifiedEmail(values.email);
          return;
        }
        const mapped = fieldErrorsFrom(error.problem, FIELDS);
        for (const [field, message] of Object.entries(mapped.fields)) {
          setError(field as (typeof FIELDS)[number], { message: message as string });
        }
        setFormError(mapped.form);
      },
    });
  });

  return (
    <>
      <h1 className="text-3xl leading-tight">Welcome back</h1>
      <p className="mt-2 text-ink-soft">Log in with your UofM email to find or offer a ride.</p>

      <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-4">
        {formError && <FormAlert>{formError}</FormAlert>}

        {unverifiedEmail && (
          <div role="alert" className="rounded-md bg-surface-muted p-4">
            <p className="flex items-center gap-2 font-bold">
              <MailWarning aria-hidden="true" className="size-5 shrink-0" />
              Verify your email first
            </p>
            <p className="mt-1 text-sm text-ink-soft">
              Open the link we sent to <strong className="text-ink">{unverifiedEmail}</strong> when you
              signed up, then log in.
            </p>
            <ResendButton email={unverifiedEmail} variant="secondary" size="sm" className="mt-3" />
          </div>
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
        <TextField
          compact
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />

        <Button type="submit" size="md" fullWidth loading={login.isPending} className="mt-1">
          Log in
        </Button>
      </form>

      <p className="mt-5 border-t border-line pt-4 text-center text-ink-soft">
        New to GetDrove?{" "}
        <Link href="/signup" className="font-bold text-ink underline underline-offset-4">
          Create an account
        </Link>
      </p>
    </>
  );
}
