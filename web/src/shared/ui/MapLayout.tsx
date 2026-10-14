import type { ReactNode } from "react";

/**
 * The layout of most screens in the mockups.
 *
 * - Desktop: the panel on the left, the map filling the rest of the screen.
 * - Mobile: the map at the top, the panel sliding over it like a sheet (rounded top
 *   corners and a handle), scrolling with the page.
 *
 * Put it directly under <AppHeader />.
 */
export function MapLayout({ panel, map }: { panel: ReactNode; map: ReactNode }) {
  return (
    <div className="md:grid md:h-[calc(100dvh-4.5rem)] md:grid-cols-[minmax(22rem,33rem)_1fr]">
      <div className="h-[42dvh] md:order-2 md:h-full">{map}</div>
      <section className="relative z-10 -mt-7 rounded-t-xl bg-surface px-5 pt-3 pb-8 shadow-sheet md:order-1 md:mt-0 md:overflow-y-auto md:rounded-none md:px-8 md:pt-8 md:shadow-none">
        <div aria-hidden="true" className="mx-auto mb-6 h-1.5 w-12 rounded-full bg-line md:hidden" />
        {panel}
      </section>
    </div>
  );
}
