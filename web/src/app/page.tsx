import { ServiceStatus } from "@/features/status";

// Placeholder home page for the walking skeleton: proves the browser reaches every
// service through the gateway. Replaced by the rider home screen.
export default function HomePage() {
  return (
    <main>
      <h1>GetDrove</h1>
      <p>Carpooling for UofM students. Coming soon.</p>
      <ServiceStatus />
    </main>
  );
}
