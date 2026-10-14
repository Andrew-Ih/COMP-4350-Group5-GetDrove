"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Drawer } from "vaul";

export type BottomSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Read by screen readers when the sheet opens. Visually hidden if `hideTitle`. */
  title: string;
  hideTitle?: boolean;
  children: ReactNode;
};

/**
 * A panel that slides up from the bottom and can be dragged down to close, e.g. the
 * rating sheet. On wide screens it's centred and limited in width.
 * Built on vaul, which handles dragging, focus and the Escape key.
 */
export function BottomSheet({ open, onOpenChange, title, hideTitle = false, children }: BottomSheetProps) {
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-ink/50" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[92dvh] w-full max-w-xl flex-col rounded-t-xl bg-surface outline-none">
          <div aria-hidden="true" className="mx-auto mt-3 h-1.5 w-12 shrink-0 rounded-full bg-line" />
          <Drawer.Close
            aria-label="Close"
            className="absolute top-5 right-5 flex size-11 items-center justify-center rounded-full bg-surface-muted"
          >
            <X className="size-5" />
          </Drawer.Close>
          <div className="overflow-y-auto px-6 pt-6 pb-[max(env(safe-area-inset-bottom),2rem)]">
            <Drawer.Title className={hideTitle ? "sr-only" : "mb-4 pr-12 text-2xl font-extrabold"}>
              {title}
            </Drawer.Title>
            {children}
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
