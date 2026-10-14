"use client";

import { Star } from "lucide-react";
import { useState } from "react";

import { Avatar, BottomSheet, Button, PrivacyNote, TextField } from "@/shared/ui";

export function SheetDemo() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="dark" size="md" onClick={() => setOpen(true)}>
        Open the rating sheet
      </Button>
      <BottomSheet open={open} onOpenChange={setOpen} title="How was your ride with Andrew?" hideTitle>
        <div className="flex flex-col items-center gap-2 text-center">
          <Avatar name="Andrew" size="lg" tone="light" />
          <p className="mt-2 text-2xl font-extrabold tracking-tight">How was your ride with Andrew?</p>
          <p className="text-ink-soft">Today · Black Mazda 3 · $4.20</p>
          <div className="my-4 flex gap-4 text-brand" aria-hidden="true">
            {[1, 2, 3, 4].map((n) => (
              <Star key={n} className="size-10 fill-current" />
            ))}
            <Star className="size-10 text-subtle" />
          </div>
        </div>
        <TextField label="Add a comment (optional)" placeholder="Anything that would help next time?" />
        <Button fullWidth className="mt-6" onClick={() => setOpen(false)}>
          Submit rating
        </Button>
        <PrivacyNote className="mt-4 justify-center">Andrew sees your rating, never your name or address.</PrivacyNote>
      </BottomSheet>
    </>
  );
}
