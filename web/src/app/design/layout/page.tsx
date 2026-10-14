import { ArrowRight, Clock } from "lucide-react";
import type { Metadata } from "next";

import { MapView } from "@/shared/map";
import { AppHeader, Button, Card, MapLayout, PrivacyNote } from "@/shared/ui";

import { sampleArea, sampleMarkers } from "../sample-route";

export const metadata: Metadata = {
  title: "Map layout · Design system · GetDrove",
  robots: { index: false },
};

/** The panel + map layout most screens use. Resize the window to see the mobile version. */
export default function LayoutDemoPage() {
  return (
    <>
      <AppHeader userName="Maya" />
      <MapLayout
        map={<MapView area={sampleArea} markers={sampleMarkers.filter((m) => m.kind !== "pickup")} />}
        panel={
          <div className="flex flex-col gap-5">
            <div>
              <p className="text-lg text-ink-soft">Good evening, Maya</p>
              <h1 className="text-4xl md:text-5xl">Where are you heading?</h1>
            </div>
            <Card variant="muted" className="flex flex-col gap-4">
              <div>
                <p className="text-sm font-semibold text-ink-soft">Pickup area</p>
                <p className="text-xl font-bold">Osborne Village</p>
              </div>
              <div className="border-t border-line pt-4">
                <p className="text-sm font-semibold text-ink-soft">Destination</p>
                <p className="text-xl font-bold">U of M Fort Garry Campus</p>
              </div>
            </Card>
            <Card variant="muted" className="flex items-center gap-4">
              <Clock className="size-6" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-ink-soft">When</p>
                <p className="text-xl font-bold">Tomorrow, arrive by 8:30 AM</p>
              </div>
            </Card>
            <Button fullWidth>
              Find rides <ArrowRight className="size-5" />
            </Button>
            <PrivacyNote>Only your general area is used. You&apos;ll meet drivers at a pickup point on their route.</PrivacyNote>
          </div>
        }
      />
    </>
  );
}
