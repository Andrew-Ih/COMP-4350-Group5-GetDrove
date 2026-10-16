"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";

import { getAccessToken } from "@/shared/api";

const noSubscription = () => () => {};
const hasToken = () => Boolean(getAccessToken());
// While the page is rendered on the server there's no token, so nothing is shown yet;
// the browser then checks for real.
const onServer = () => false;

/**
 * Shows its children only to a logged-in student; everyone else is sent to /login and
 * brought back here afterwards. The access token lives in memory, so a reload also means
 * logging in again until refresh (#90) is built. Real protection is on the server: every
 * API call checks the token.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const loggedIn = useSyncExternalStore(noSubscription, hasToken, onServer);

  useEffect(() => {
    if (!loggedIn) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loggedIn, router, pathname]);

  return loggedIn ? children : null;
}
