import { ArrowRight, Download, MessageCircle, Share2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { MapView } from "@/shared/map";
import { AppHeader, Avatar, Badge, Button, Card, Eyebrow, PrivacyNote, TextField } from "@/shared/ui";

import { sampleArea, sampleMarkers, sampleRoutes } from "./sample-route";
import { SheetDemo } from "./SheetDemo";

export const metadata: Metadata = {
  title: "Design system · GetDrove",
  robots: { index: false },
};

const COLORS = [
  ["ink", "bg-ink", "Headings, primary text, dark cards"],
  ["ink-soft", "bg-ink-soft", "Body text"],
  ["muted", "bg-muted", "Secondary text"],
  ["subtle", "bg-subtle", "Placeholders, disabled text"],
  ["line-strong", "bg-line-strong", "Secondary button borders"],
  ["line", "bg-line", "Borders, dividers, disabled"],
  ["surface-muted", "bg-surface-muted", "Inputs, info boxes"],
  ["canvas", "bg-canvas", "Page background behind cards"],
  ["brand", "bg-brand", "Primary actions, selected route"],
  ["brand-light", "bg-brand-light", "Rest of a route"],
  ["brand-soft", "bg-brand-soft", "Your area, avatars"],
  ["brand-tint", "bg-brand-tint", "Status badges"],
  ["danger", "bg-danger", "Form errors"],
  ["map-water", "bg-map-water", "Map water"],
] as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-10">
      <h2 className="mb-6 text-2xl">{title}</h2>
      {children}
    </section>
  );
}

/** Every design token and shared component in one place. Not linked from the app. */
export default function DesignPage() {
  return (
    <>
      <AppHeader userName="Maya" />
      <main className="mx-auto max-w-5xl px-4 py-10 md:px-8">
        <h1 className="text-4xl md:text-5xl">Design system</h1>
        <p className="mt-2 text-lg text-muted">
          Tokens and shared components from the mockups. Source: <code>src/app/globals.css</code> and{" "}
          <code>src/shared/ui</code>. Full-screen layout: <Link className="font-bold underline" href="/design/layout">/design/layout</Link>
        </p>

        <Section title="Colours">
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {COLORS.map(([name, swatch, use]) => (
              <li key={name} className="flex flex-col gap-2">
                <span className={`h-16 rounded-md border border-line ${swatch}`} />
                <span className="font-bold">{name}</span>
                <span className="text-sm text-muted">{use}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Type">
          <div className="flex flex-col gap-3">
            <p className="text-5xl font-extrabold tracking-tight">$286.40</p>
            <h1 className="text-4xl">Where are you heading?</h1>
            <h2 className="text-2xl">3 pending requests</h2>
            <p className="text-lg font-bold">Osborne St & River Ave</p>
            <p className="text-lg text-ink-soft">Share the commute to Fort Garry campus with other UofM students.</p>
            <p className="text-muted">Based on 9.2 km of a 14 km trip</p>
            <Eyebrow>Pickup · 7:48 AM</Eyebrow>
            <Eyebrow tone="muted">Drop-off · 8:12 AM</Eyebrow>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>
              Find rides <ArrowRight className="size-5" />
            </Button>
            <Button variant="dark" icon={<MessageCircle className="size-5" />}>
              Trip chat
            </Button>
            <Button variant="outline" icon={<Share2 className="size-5" />}>
              Share trip
            </Button>
            <Button variant="secondary">Decline</Button>
            <Button disabled>Accept</Button>
            <Button loading>Posting…</Button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button size="md" variant="outline" icon={<Download className="size-4" />}>
              Statement
            </Button>
            <Button size="sm" variant="soft">
              Small soft
            </Button>
          </div>
          <div className="mt-4 max-w-md">
            <Button fullWidth>Request a seat with Priya · $4.20</Button>
          </div>
        </Section>

        <Section title="Inputs">
          <div className="grid max-w-md gap-5">
            <TextField label="UofM email" type="email" placeholder="you@myumanitoba.ca" />
            <TextField label="Password" type="password" placeholder="At least 10 characters" />
            <TextField
              label="UofM email"
              type="email"
              defaultValue="maya@gmail.com"
              error="Only @myumanitoba.ca emails are accepted."
            />
          </div>
        </Section>

        <Section title="Badges and avatars">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="status" dot>
              Live
            </Badge>
            <Badge variant="status">Trip complete</Badge>
            <Badge variant="outline">Pending</Badge>
            <Badge variant="solid">Settled</Badge>
            <Badge variant="solid">3 min</Badge>
            <Badge variant="dark" className="text-lg">
              +3 min
            </Badge>
            <Badge variant="neutral">Calculating…</Badge>
          </div>
          <div className="mt-5 flex items-center gap-3">
            <Avatar name="Maya" />
            <Avatar name="Priya" tone="soft" />
            <Avatar name="Andrew" tone="dark" />
            <Avatar name="Me" tone="brand" />
            <Avatar name="Sofia" size="lg" />
            <Avatar name="Noor" size="sm" />
          </div>
        </Section>

        <Section title="Cards">
          <div className="grid gap-4 md:grid-cols-2">
            <Card variant="dark">
              <p className="text-sm text-white/80">Tue, Oct 6 · Departs 7:35 AM</p>
              <p className="mt-1 text-2xl font-extrabold">Wolseley → U of M Fort Garry</p>
              <p className="mt-2 font-bold">2 of 3 seats filled</p>
            </Card>
            <Card variant="muted" className="flex items-center justify-between">
              <div>
                <p className="font-bold">Your share</p>
                <p className="text-ink-soft">Based on 9.2 km of a 14 km trip</p>
              </div>
              <p className="text-4xl font-extrabold tracking-tight">$4.20</p>
            </Card>
            <Card>
              <div className="flex items-center gap-4">
                <Avatar name="Maya" />
                <div className="min-w-0 flex-1">
                  <p className="text-lg font-extrabold">Maya ★ 4.9 · 0 no-shows</p>
                  <p className="text-ink-soft">Osborne St & River Ave</p>
                </div>
                <Badge variant="dark" className="text-lg">
                  +3 min
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <Button variant="secondary" size="md">
                  Decline
                </Button>
                <Button size="md">Accept</Button>
              </div>
            </Card>
            <Card variant="pending">
              <div className="flex items-center gap-4">
                <Avatar name="Sofia" />
                <div className="min-w-0 flex-1">
                  <p className="text-lg font-extrabold">Sofia ★ 5.0</p>
                  <p className="text-ink-soft">Pembina Hwy & Jubilee Ave</p>
                </div>
                <Badge variant="neutral">Calculating…</Badge>
              </div>
            </Card>
            <Card variant="selected">Selected item (e.g. the chosen trip in results)</Card>
          </div>
        </Section>

        <Section title="Privacy note">
          <PrivacyNote>Drivers only see your pickup point, never your home address.</PrivacyNote>
        </Section>

        <Section title="Bottom sheet">
          <SheetDemo />
        </Section>

        <Section title="Map">
          <div className="h-[28rem] overflow-hidden rounded-lg border border-line">
            <MapView routes={sampleRoutes} markers={sampleMarkers} area={sampleArea} />
          </div>
          <p className="mt-3 text-sm text-muted">
            Route styles: primary (green), light, other (grey), hidden (dashed), walk (dotted). Markers: pickup,
            campus, you, stop. The dashed circle is the rider&apos;s private area.
          </p>
        </Section>
      </main>
    </>
  );
}
