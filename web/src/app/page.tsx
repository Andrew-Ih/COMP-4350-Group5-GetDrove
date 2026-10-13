import { ServiceStatus } from "@/features/status";
import { Card, Logo } from "@/shared/ui";

// Placeholder home page for the walking skeleton: proves the browser reaches every
// service through the gateway. Replaced by the rider home screen.
export default function HomePage() {
  return (
    <main className="min-h-dvh bg-canvas px-4 py-12">
      <Card className="mx-auto max-w-md bg-surface p-8">
        <Logo className="text-3xl" />
        <h1 className="mt-6 text-3xl">A seat that&apos;s actually yours</h1>
        <p className="mt-2 text-lg text-ink-soft">Carpooling for UofM students. Coming soon.</p>
        <div className="mt-6">
          <ServiceStatus />
        </div>
      </Card>
    </main>
  );
}
