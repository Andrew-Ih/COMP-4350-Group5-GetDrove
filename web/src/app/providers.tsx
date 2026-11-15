"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { type ReactNode, useState } from "react";

import { NotificationBell } from "@/features/notifications";
import { retryServerErrors } from "@/shared/api";
import { HeaderBellContext } from "@/shared/ui";

const mocking = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";

// Browser only (ssr: false): the mock API can't run on the server, and this keeps it
// out of the server build entirely.
const MockApi = dynamic(() => import("@/shared/mocks/MockApi").then((m) => m.MockApi), {
  ssr: false,
});

/**
 * App-wide providers: data fetching (TanStack Query), the notification bell for the header,
 * and, when turned on, the mock API. A failed load is tried again once, only for server
 * errors (#39); queries that should never retry say so themselves.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: retryServerErrors } } }),
  );

  const content = (
    <QueryClientProvider client={queryClient}>
      <HeaderBellContext.Provider value={<NotificationBell />}>{children}</HeaderBellContext.Provider>
    </QueryClientProvider>
  );
  return mocking ? <MockApi>{content}</MockApi> : content;
}
