"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";

import { getAccessToken, refreshSession, subscribeToSession } from "@/shared/api";
import { Spinner } from "@/shared/ui";

const hasToken = () => Boolean(getAccessToken());
// While the page is rendered on the server there's no session, so nothing is shown yet;
// the browser then checks for real.
const onServer = () => false;

/**
 * Shows its children only to a logged-in student.
 *
 * After a reload the access token (kept in memory) is gone, so this first tries the
 * refresh cookie: if it still works, the student stays logged in without noticing.
 * Otherwise they're sent to /login and brought back here afterwards. It also reacts to
 * logging out, in this tab or another. Real protection is on the server: every API call
 * checks the token.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const loggedIn = useSyncExternalStore(subscribeToSession, hasToken, onServer);

  useEffect(() => {
    if (loggedIn) return;
    let cancelled = false;
    void refreshSession().then((ok) => {
      // Keep the query too, e.g. a search on /ride/results, so the student comes back to it.
      if (!ok && !cancelled) {
        router.replace(`/login?next=${encodeURIComponent(`${pathname}${window.location.search}`)}`);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loggedIn, router, pathname]);

  if (loggedIn) return children;
  return (
    <div role="status" className="flex min-h-dvh items-center justify-center gap-3 font-semibold text-ink-soft">
      <Spinner className="size-5" /> Loading…
    </div>
  );
}
