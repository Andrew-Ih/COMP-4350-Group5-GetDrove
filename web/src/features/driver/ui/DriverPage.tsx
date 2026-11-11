"use client";

import { CheckCircle2, Clock, FileText, XCircle } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { useCurrentUser } from "@/features/auth";
import type { ApiError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { AppHeader, Button, buttonStyles, PrivacyNote, Spinner, TextField } from "@/shared/ui";

import { useDriverProfile, useOpenDocument, useSaveVehicle, useUploadDocuments } from "../hooks/useDriver";
import {
  buildVehicle,
  DOCUMENT_LABEL,
  type DocumentKind,
  type DriverProfile,
  fileProblem,
  serverFieldErrors,
  statusMessage,
  uploadError,
  type VehicleField,
  type VehicleForm,
} from "../model/driver";

/**
 * The driver page (#12, #126): where a student applies to drive and sees where it stands.
 * They upload their licence and insurance and add their vehicle; an admin approves or
 * rejects them (#128). Only the student and admins can open the documents.
 */
export function DriverPage() {
  const me = useCurrentUser();
  const profile = useDriverProfile();

  return (
    <>
      <AppHeader userName={me.data?.firstName ?? ""} />
      <main className="mx-auto max-w-xl px-5 py-8 md:py-12">
        <h1 className="text-3xl md:text-4xl">Driving with GetDrove</h1>

        {profile.status === "pending" && (
          <p role="status" className="mt-8 flex items-center gap-3 font-semibold text-ink-soft">
            <Spinner className="size-5" /> Loading…
          </p>
        )}
        {profile.status === "error" && <LoadError error={profile.error} onRetry={() => void profile.refetch()} />}
        {profile.status === "success" && (
          <>
            <StatusCard profile={profile.data} />
            <Documents profile={profile.data} />
            <VehicleSection profile={profile.data} />
            <PrivacyNote className="mt-8">Only you and GetDrove admins can see your documents. Riders only see your car once you accept them.</PrivacyNote>
          </>
        )}
      </main>
    </>
  );
}

const STATUS_LOOK = {
  none: { box: "border-line", icon: FileText, iconClass: "text-ink" },
  pending: { box: "border-line bg-surface-muted", icon: Clock, iconClass: "text-ink" },
  approved: { box: "border-brand bg-brand-tint", icon: CheckCircle2, iconClass: "text-brand" },
  rejected: { box: "border-danger bg-danger-tint", icon: XCircle, iconClass: "text-danger" },
} as const;

function StatusCard({ profile }: { profile: DriverProfile }) {
  const { title, text } = statusMessage(profile);
  const look = STATUS_LOOK[profile.status];
  const Icon = look.icon;
  const missingVehicle = profile.status === "pending" && !profile.vehicle;
  return (
    <div role="status" className={cn("mt-6 flex gap-3 rounded-lg border-2 px-5 py-4", look.box)}>
      <Icon aria-hidden="true" className={cn("mt-0.5 size-6 shrink-0", look.iconClass)} />
      <div className="min-w-0">
        <p className="text-lg font-bold">{title}</p>
        <p className="text-ink-soft">
          {profile.status === "rejected" && <span className="font-semibold text-ink">Reason: </span>}
          {text}
        </p>
        {profile.status === "rejected" && <p className="mt-1 text-ink-soft">Upload new documents below to apply again.</p>}
        {missingVehicle && <p className="mt-1 font-semibold">Add your vehicle below too: you can&apos;t be approved without it.</p>}
        {profile.status === "approved" && (
          <Link href="/drive/new" className={cn(buttonStyles({ size: "sm" }), "mt-3")}>
            Post a trip
          </Link>
        )}
      </div>
    </div>
  );
}

function Documents({ profile }: { profile: DriverProfile }) {
  const uploaded = profile.documents.licence && profile.documents.insurance;
  const [replacing, setReplacing] = useState(false);
  const canUpload = profile.status !== "approved";
  const showForm = canUpload && (!uploaded || replacing || profile.status === "rejected");

  return (
    <section aria-label="Documents" className="mt-10">
      <h2 className="text-xl">Documents</h2>
      {uploaded && (
        <ul className="mt-3 space-y-2">
          {(["licence", "insurance"] as const).map((kind) => (
            <UploadedDocument key={kind} kind={kind} />
          ))}
        </ul>
      )}
      {showForm ? (
        <UploadForm
          replacing={uploaded}
          onDone={() => setReplacing(false)}
          onCancel={uploaded && replacing ? () => setReplacing(false) : undefined}
        />
      ) : (
        canUpload && (
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => setReplacing(true)}>
            Replace documents
          </Button>
        )
      )}
    </section>
  );
}

function UploadedDocument({ kind }: { kind: DocumentKind }) {
  const open = useOpenDocument();
  return (
    <li className="flex items-center justify-between gap-3 rounded-md border-2 border-line px-4 py-3">
      <span className="flex items-center gap-2 font-semibold">
        <CheckCircle2 aria-hidden="true" className="size-5 text-brand" /> {DOCUMENT_LABEL[kind]}
      </span>
      <span className="flex items-center gap-3">
        {open.isError && <span className="text-sm text-danger">Couldn&apos;t open it</span>}
        <Button variant="secondary" size="sm" loading={open.isPending} onClick={() => open.mutate(kind)} aria-label={`View ${DOCUMENT_LABEL[kind]}`}>
          View
        </Button>
      </span>
    </li>
  );
}

function UploadForm({ replacing, onDone, onCancel }: { replacing: boolean; onDone: () => void; onCancel?: () => void }) {
  const upload = useUploadDocuments();
  const [files, setFiles] = useState<Partial<Record<DocumentKind, File>>>({});
  const [problems, setProblems] = useState<Partial<Record<DocumentKind, string>>>({});
  const ready = Boolean(files.licence && files.insurance) && !problems.licence && !problems.insurance;

  function choose(kind: DocumentKind, file: File | undefined) {
    setFiles((f) => ({ ...f, [kind]: file }));
    setProblems((p) => ({ ...p, [kind]: file ? fileProblem(file) : undefined }));
    upload.reset();
  }

  return (
    <form
      className="mt-4 space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (files.licence && files.insurance) upload.mutate({ licence: files.licence, insurance: files.insurance }, { onSuccess: onDone });
      }}
    >
      {(["licence", "insurance"] as const).map((kind) => (
        <FileField key={kind} kind={kind} file={files[kind]} problem={problems[kind]} onChoose={(file) => choose(kind, file)} />
      ))}
      <p className="text-sm text-ink-soft">
        {/* The contract takes both files together, so one can't be replaced on its own. */}
        {replacing && "Upload both files again, even if only one has changed. "}
        PDF, JPEG or PNG, up to 5 MB each.
      </p>
      {upload.error && (
        <p role="alert" className="rounded-md bg-danger-tint px-4 py-3 font-semibold text-danger">
          {uploadError(upload.error.code)}
        </p>
      )}
      <Button type="submit" fullWidth disabled={!ready} loading={upload.isPending}>
        Upload documents
      </Button>
      {onCancel && (
        <Button type="button" variant="secondary" size="md" fullWidth onClick={onCancel}>
          Keep my current documents
        </Button>
      )}
    </form>
  );
}

function FileField({
  kind,
  file,
  problem,
  onChoose,
}: {
  kind: DocumentKind;
  file: File | undefined;
  problem: string | undefined;
  onChoose: (file: File | undefined) => void;
}) {
  const id = `document-${kind}`;
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-bold">
        {DOCUMENT_LABEL[kind]}
      </label>
      <input
        id={id}
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? `${id}-problem` : undefined}
        onChange={(event) => onChoose(event.target.files?.[0])}
        className="block w-full rounded-md border-2 border-dashed border-line-strong px-4 py-3 text-ink-soft file:mr-4 file:rounded-md file:border-0 file:bg-ink file:px-4 file:py-2 file:font-bold file:text-white"
      />
      {file && !problem && <p className="mt-1 text-sm text-ink-soft">{file.name}</p>}
      {problem && (
        <p id={`${id}-problem`} className="mt-1 text-sm font-semibold text-danger">
          {problem}
        </p>
      )}
    </div>
  );
}

function VehicleSection({ profile }: { profile: DriverProfile }) {
  const [editing, setEditing] = useState(false);
  const vehicle = profile.vehicle;

  return (
    <section aria-label="Vehicle" className="mt-10">
      <h2 className="text-xl">Vehicle</h2>
      {vehicle && !editing ? (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-md border-2 border-line px-4 py-3">
          <div>
            <p className="font-bold">
              {vehicle.colour} {vehicle.make} {vehicle.model}
            </p>
            <p className="text-ink-soft">Plate {vehicle.plate}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      ) : (
        <VehicleEditor
          initial={vehicle ?? undefined}
          onDone={() => setEditing(false)}
          onCancel={vehicle ? () => setEditing(false) : undefined}
        />
      )}
    </section>
  );
}

function VehicleEditor({
  initial,
  onDone,
  onCancel,
}: {
  initial: VehicleForm | undefined;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const save = useSaveVehicle();
  const [form, setForm] = useState<VehicleForm>(initial ?? { make: "", model: "", colour: "", plate: "" });
  const [errors, setErrors] = useState<Partial<Record<VehicleField, string>>>({});

  function field(name: VehicleField, label: string, hint?: string) {
    return (
      <TextField
        label={label}
        hint={hint}
        value={form[name]}
        error={errors[name]}
        compact
        onChange={(event) => {
          setForm((f) => ({ ...f, [name]: event.target.value }));
          setErrors((e) => ({ ...e, [name]: undefined }));
        }}
      />
    );
  }

  return (
    <form
      noValidate
      className="mt-3 space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const built = buildVehicle(form);
        if ("errors" in built) {
          setErrors(built.errors);
          return;
        }
        save.mutate(built.vehicle, {
          onSuccess: onDone,
          onError: (error) => setErrors(serverFieldErrors(error.problem.errors)),
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {field("make", "Make", "e.g. Honda")}
        {field("model", "Model", "e.g. Civic")}
        {field("colour", "Colour", "e.g. Grey")}
        {field("plate", "Licence plate", "Shown only to riders you accept")}
      </div>
      {save.error && Object.keys(serverFieldErrors(save.error.problem.errors)).length === 0 && (
        <p role="alert" className="rounded-md bg-danger-tint px-4 py-3 font-semibold text-danger">
          We couldn&apos;t save your vehicle. Try again.
        </p>
      )}
      <div className="flex gap-3">
        <Button type="submit" size="md" loading={save.isPending}>
          Save vehicle
        </Button>
        {onCancel && (
          <Button type="button" variant="secondary" size="md" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

function LoadError({ error, onRetry }: { error: ApiError | null; onRetry: () => void }): ReactNode {
  if (error?.code === "unauthorized") {
    return (
      <div role="alert" className="mt-8 space-y-3 text-ink-soft">
        <p>Your session has ended. Log in again to see your driver status.</p>
        <Link href="/login?next=%2Faccount%2Fdriver" className={buttonStyles({ size: "md" })}>
          Log in
        </Link>
      </div>
    );
  }
  return (
    <div role="alert" className="mt-8 space-y-3 text-ink-soft">
      <p>We couldn&apos;t load your driver status.</p>
      <Button size="md" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
