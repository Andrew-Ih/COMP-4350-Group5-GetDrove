"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Bell, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { logOut } from "@/shared/api";
import { cn } from "@/shared/lib/cn";

import { Avatar } from "./Avatar";
import { Logo } from "./Logo";

const NAV = [
  { href: "/ride", label: "Ride", match: "/ride" },
  { href: "/drive/new", label: "Drive", match: "/drive" },
  { href: "/trips", label: "My trips", match: "/trips" },
] as const;

/**
 * Top bar on every signed-in screen. Desktop: logo, Ride / Drive / My trips, bell, and the
 * avatar, which opens a menu with Log out. Mobile: logo, avatar and a menu button that
 * opens the same links and Log out.
 */
export function AppHeader({ userName }: { userName: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const accountMenu = useRef<HTMLDivElement>(null);

  // Close the account menu when clicking anywhere else.
  useEffect(() => {
    if (!accountOpen) return;
    const close = (event: PointerEvent) => {
      if (!accountMenu.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [accountOpen]);

  async function handleLogOut() {
    setLoggingOut(true);
    await logOut();
    queryClient.clear(); // nothing from this student's session stays in memory
    router.replace("/login");
  }

  const links = NAV.map((item) => {
    const active = pathname.startsWith(item.match);
    return { ...item, active };
  });
  const onNotifications = pathname.startsWith("/notifications");

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
          <Link
            href="/notifications"
            aria-label="Notifications"
            aria-current={onNotifications ? "page" : undefined}
            className={cn(
              "hidden rounded-full p-2 transition-colors hover:bg-surface-muted hover:text-ink md:block",
              onNotifications ? "text-ink" : "text-muted",
            )}
          >
            <Bell className="size-6" />
          </Link>
          <div ref={accountMenu} className="relative">
            <button
              type="button"
              aria-label="Account"
              aria-haspopup="menu"
              aria-expanded={accountOpen}
              onClick={() => setAccountOpen((open) => !open)}
              className="block rounded-full"
            >
              <Avatar name={userName} tone="dark" />
            </button>
            {accountOpen && (
              <div role="menu" className="absolute top-full right-0 mt-2 w-56 rounded-md bg-surface py-2 shadow-card">
                {userName && <p className="truncate px-4 pt-1 pb-2 text-sm text-ink-soft">Logged in as {userName}</p>}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => void handleLogOut()}
                  disabled={loggingOut}
                  className="flex w-full items-center gap-2 px-4 py-2.5 text-left font-semibold hover:bg-surface-muted"
                >
                  <LogOut aria-hidden="true" className="size-4" /> {loggingOut ? "Logging out…" : "Log out"}
                </button>
              </div>
            )}
          </div>
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
          <Link
            href="/notifications"
            aria-current={onNotifications ? "page" : undefined}
            onClick={() => setMenuOpen(false)}
            className={cn(
              "block border-b border-line py-4 text-lg font-semibold",
              onNotifications ? "text-ink" : "text-muted",
            )}
          >
            Notifications
          </Link>
          <button
            type="button"
            onClick={() => void handleLogOut()}
            disabled={loggingOut}
            className="flex w-full items-center gap-2 py-4 text-left text-lg font-semibold text-muted"
          >
            <LogOut aria-hidden="true" className="size-5" /> {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </nav>
      )}
    </header>
  );
}
