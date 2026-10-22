import type { Metadata } from "next";

import { ServiceStatus } from "@/features/status";
import { Card, Logo } from "@/shared/ui";

export const metadata: Metadata = { title: "Service status · GetDrove" };

/**
 * /status: whether every backend service answers through the gateway. For the team (after
 * a deploy, before a demo); students never need it, so nothing links here.
 */
export default function StatusPage() {
  return (
    <main className="min-h-dvh bg-canvas px-4 py-12">
      <Card className="mx-auto max-w-md bg-surface p-8">
        <Logo className="text-3xl" />
        <h1 className="mt-6 text-3xl">Service status</h1>
        <p className="mt-2 text-lg text-ink-soft">Each service, checked through the gateway.</p>
        <div className="mt-6">
          <ServiceStatus />
        </div>
      </Card>
    </main>
  );
}
