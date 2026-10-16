"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { GraduationCap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button, TextField } from "@/shared/ui";

import { useSignup } from "../hooks/useAuthMutations";
import { fieldErrorsFrom } from "../model/serverErrors";
import { signupSchema, type SignupValues } from "../model/signup";
import { CheckEmail } from "./CheckEmail";
import { FormAlert } from "./FormAlert";

const FIELDS = ["firstName", "lastName", "email", "password"] as const;

/** Sign up with a UofM email (#7). On success, shows "Check your email". */
export function SignupForm() {
  const signup = useSignup();
  const [formError, setFormError] = useState<string>();
  const [sentTo, setSentTo] = useState<string>();
  const [emailTaken, setEmailTaken] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { firstName: "", lastName: "", email: "", password: "" },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(undefined);
    setEmailTaken(false);
    signup.mutate(values, {
      onSuccess: (account) => setSentTo(account.email),
      onError: (error) => {
        if (error.code === "email_taken") {
          setEmailTaken(true);
          setError("email", { message: "An account with this email already exists." });
          return;
        }
        if (error.code === "email_not_uofm") {
          setError("email", { message: "Use your @myumanitoba.ca email." });
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

  if (sentTo) {
    return <CheckEmail email={sentTo} onStartOver={() => setSentTo(undefined)} />;
  }

  return (
    <>
      <h1 className="text-3xl leading-tight">A seat that&apos;s actually yours</h1>
      <p className="mt-2 text-ink-soft">
        Share the commute to Fort Garry campus with other UofM students.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-4">
        {formError && <FormAlert>{formError}</FormAlert>}

        <div className="grid grid-cols-2 gap-3">
          <TextField
            compact
            label="First name"
            autoComplete="given-name"
            error={errors.firstName?.message}
            {...register("firstName")}
          />
          <TextField
            compact
            label="Last name"
            autoComplete="family-name"
            error={errors.lastName?.message}
            {...register("lastName")}
          />
        </div>

        <div>
          <TextField
            compact
            label="UofM email"
            type="email"
            autoComplete="email"
            placeholder="you@myumanitoba.ca"
            error={errors.email?.message}
            {...register("email")}
          />
          {emailTaken && (
            <p className="mt-2 text-sm">
              <Link href="/login" className="font-bold underline underline-offset-4">
                Log in instead
              </Link>
            </p>
          )}
        </div>

        <TextField
          compact
          label="Password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 10 characters"
          error={errors.password?.message}
          {...register("password")}
        />

        <Button type="submit" size="md" fullWidth loading={signup.isPending} className="mt-1">
          Create account
        </Button>
      </form>

      <p className="mt-4 flex items-start gap-2.5 text-sm text-ink-soft">
        <GraduationCap aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink" />
        <span>
          Only UofM student emails (@myumanitoba.ca) are accepted. We&apos;ll send a link to verify yours.
        </span>
      </p>

      <p className="mt-5 border-t border-line pt-4 text-center text-ink-soft">
        Already have an account?{" "}
        <Link href="/login" className="font-bold text-ink underline underline-offset-4">
          Log in
        </Link>
      </p>
    </>
  );
}
