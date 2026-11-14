"use client";

import { FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { AppHeader, Button, buttonStyles, Card, Spinner } from "@/shared/ui";

import { useAdminDrivers, useDecideDriver, useOpenApplicantDocument } from "../hooks/useDriver";
import {
  type AdminDriver,
  type AdminDriverStatus,
  decisionError,
  DOCUMENT_LABEL,
  type DocumentKind,
  isAdmin,
  MAX_REASON_LENGTH,
  reasonProblem,
  vehicleLine,
} from "../model/driver";

const TABS: { status: AdminDriverStatus; label: string }[] = [
  { status: "pending", label: "Pending" },
  { status: "approved", label: "Approved" },
  { status: "rejected", label: "Rejected" },
];

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—";

/**
 * The admin page for driver applications (#128): pending ones oldest first, with the
 * applicant's vehicle and documents, and Approve or Reject (with a reason the driver sees).
 * Only for admins: anyone else is sent to the home page, and the API refuses them anyway.
 */
export function AdminDrivers() {
  const me = useCurrentUser();
  const router = useRouter();
  const admin = isAdmin(me.data);
  const [status, setStatus] = useState<AdminDriverStatus>("pending");
  const drivers = useAdminDrivers(status, admin);

  useEffect(() => {
    if (me.isSuccess && !admin) router.replace("/");
  }, [me.isSuccess, admin, router]);

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-3xl px-5 py-8 md:py-12">
        <h1 className="text-3xl md:text-4xl">Driver applications</h1>

        {me.isPending && (
          <p role="status" className="mt-8 flex items-center gap-3 font-semibold text-ink-soft">
            <Spinner className="size-5" /> Loading…
          </p>
        )}
        {me.isSuccess && !admin && (
          <p role="alert" className="mt-8 font-semibold">
            Only admins can see this page.
          </p>
        )}

        {admin && (
          <>
            <div role="tablist" aria-label="Status" className="mt-6 grid grid-cols-3 gap-1 rounded-md bg-surface-muted p-1">
              {TABS.map((tab) => (
                <button
                  key={tab.status}
                  type="button"
                  role="tab"
                  aria-selected={status === tab.status}
                  onClick={() => setStatus(tab.status)}
                  className={cn(
                    "h-10 rounded-sm font-bold transition-colors",
                    status === tab.status ? "bg-ink text-white" : "text-ink-soft hover:text-ink",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {drivers.isPending && (
              <p role="status" className="mt-8 flex items-center gap-3 font-semibold text-ink-soft">
                <Spinner className="size-5" /> Loading applications…
              </p>
            )}
            {drivers.isError && <LoadError error={drivers.error} onRetry={() => void drivers.refetch()} />}
            {drivers.isSuccess && drivers.data.length === 0 && (
              <p className="mt-8 text-ink-soft">
                {status === "pending" ? "No applications are waiting. You're all caught up." : `No ${status} applications yet.`}
              </p>
            )}
            {drivers.isSuccess && drivers.data.length > 0 && (
              <ul aria-label={`${TABS.find((t) => t.status === status)!.label} applications`} className="mt-6 space-y-4">
                {drivers.data.map((driver) => (
                  <li key={driver.userId}>
                    <Application driver={driver} />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>
    </>
  );
}

function Application({ driver }: { driver: AdminDriver }) {
  const decide = useDecideDriver();
  const open = useOpenApplicantDocument();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string>();
  const name = `${driver.firstName} ${driver.lastName}`;
  const pending = driver.status === "pending";

  function reject() {
    const wrong = reasonProblem(reason);
    if (wrong) {
      setProblem(wrong);
      return;
    }
    setProblem(undefined);
    decide.mutate({ userId: driver.userId, approve: false, reason: reason.trim() });
  }

  return (
    <Card aria-label={name} role="group">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl">{name}</h2>
        <span className="text-sm text-ink-soft">Submitted {when(driver.submittedAt)}</span>
      </div>
      <p className="text-ink-soft">{driver.email}</p>
      <p className={cn("mt-2 font-semibold", !driver.vehicle && "text-danger")}>{vehicleLine(driver.vehicle)}</p>

      <div className="mt-3 flex flex-wrap gap-2">
        {(["licence", "insurance"] as DocumentKind[]).map((kind) =>
          driver.documents[kind] ? (
            <Button
              key={kind}
              variant="secondary"
              size="md"
              onClick={() => open.mutate({ userId: driver.userId, kind })}
              aria-label={`View ${DOCUMENT_LABEL[kind].toLowerCase()} for ${name}`}
            >
              <FileText aria-hidden="true" className="size-4" /> {DOCUMENT_LABEL[kind]}
            </Button>
          ) : (
            <span key={kind} className="rounded-md border-2 border-dashed border-line px-4 py-2 font-semibold text-ink-soft">
              No {DOCUMENT_LABEL[kind].toLowerCase()}
            </span>
          ),
        )}
      </div>
      {open.isError && (
        <p role="alert" className="mt-2 text-sm font-semibold text-danger">
          {open.error.code === "document_not_found" ? "That document isn't there anymore." : "We couldn't open that document. Try again."}
        </p>
      )}

      {!pending && (
        <p className="mt-3 text-ink-soft">
          {driver.status === "approved" ? "Approved" : "Rejected"} {when(driver.reviewedAt)}
          {driver.rejectionReason ? `: “${driver.rejectionReason}”` : ""}
        </p>
      )}

      {pending && !rejecting && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Button size="md" loading={decide.isPending} onClick={() => decide.mutate({ userId: driver.userId, approve: true })}>
            Approve
          </Button>
          <Button variant="secondary" size="md" disabled={decide.isPending} onClick={() => setRejecting(true)}>
            Reject
          </Button>
        </div>
      )}

      {pending && rejecting && (
        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="font-bold">Why are you rejecting this application?</span>
            <span className="block text-sm text-ink-soft">{name.split(" ")[0]} will see this, so say what to fix.</span>
            <textarea
              value={reason}
              maxLength={MAX_REASON_LENGTH}
              rows={3}
              aria-invalid={problem ? true : undefined}
              onChange={(event) => {
                setReason(event.target.value);
                setProblem(undefined);
              }}
              className={cn(
                "mt-2 w-full rounded-md border-2 px-3 py-2 outline-none focus:border-ink",
                problem ? "border-danger" : "border-line",
              )}
            />
          </label>
          {problem && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {problem}
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Button
              variant="secondary"
              size="md"
              disabled={decide.isPending}
              onClick={() => {
                setRejecting(false);
                setProblem(undefined);
              }}
            >
              Cancel
            </Button>
            <Button variant="dark" size="md" loading={decide.isPending} onClick={reject}>
              Reject application
            </Button>
          </div>
        </div>
      )}

      {decide.isError && (
        <p role="alert" className="mt-3 text-sm font-semibold text-danger">
          {decisionError(decide.error.code)}
        </p>
      )}
    </Card>
  );
}

function LoadError({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  if (error.code === "unauthorized") {
    return (
      <div role="alert" className="mt-8 space-y-4">
        <p className="font-bold">Your session has ended.</p>
        <Link href="/login?next=%2Fadmin%2Fdrivers" className={buttonStyles({ size: "md" })}>
          Log in
        </Link>
      </div>
    );
  }
  return (
    <div role="alert" className="mt-8 space-y-4">
      <p className="font-bold">{error.code === "forbidden" ? "Only admins can see this page." : "We couldn't load the applications."}</p>
      {error.code !== "forbidden" && (
        <Button size="md" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
