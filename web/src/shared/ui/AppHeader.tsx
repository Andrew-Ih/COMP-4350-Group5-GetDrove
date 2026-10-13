"use client";

import { Bell, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { cn } from "@/shared/lib/cn";

import { Avatar } from "./Avatar";
import { Logo } from "./Logo";

const NAV = [
  { href: "/ride", label: "Ride", match: "/ride" },
  { href: "/drive/new", label: "Drive", match: "/drive" },
  { href: "/trips", label: "My trips", match: "/trips" },
] as const;

/**
 * Top bar on every signed-in screen. Desktop: logo, Ride / Drive / My trips, bell, avatar.
 * Mobile: logo, avatar and a menu button that opens the same links.
 */
export function AppHeader({ userName }: { userName: string }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const links = NAV.map((item) => {
    const active = pathname.startsWith(item.match);
    return { ...item, active };
  });

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      <div className="flex h-16 items-center gap-10 px-4 md:h-[4.5rem] md:px-8">
        <Link href="/" aria-label="GetDrove home">
          <Logo />
        </Link>

        <nav aria-label="Main" className="hidden h-full items-stretch gap-2 md:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={link.active ? "page" : undefined}
              className={cn(
                "flex items-center border-b-[3px] px-3 text-lg font-semibold",
                link.active
                  ? "border-ink text-ink"
                  : "border-transparent text-muted hover:text-ink",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3 md:gap-6">
          <button type="button" aria-label="Notifications" className="hidden p-2 md:block">
            <Bell className="size-6" />
          </button>
          <Avatar name={userName} tone="dark" />
          <button
            type="button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="p-2 md:hidden"
          >
            {menuOpen ? <X className="size-7" /> : <Menu className="size-7" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav aria-label="Main" className="border-t border-line px-4 pb-4 md:hidden">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={link.active ? "page" : undefined}
              onClick={() => setMenuOpen(false)}
              className={cn(
                "block border-b border-line py-4 text-lg font-semibold",
                link.active ? "text-ink" : "text-muted",
              )}
            >
              {link.label}
            </Link>
          ))}
          <Link href="/notifications" onClick={() => setMenuOpen(false)} className="block py-4 text-lg font-semibold text-muted">
            Notifications
          </Link>
        </nav>
      )}
    </header>
  );
}
