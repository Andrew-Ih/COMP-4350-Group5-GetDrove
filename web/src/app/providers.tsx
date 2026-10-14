"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { type ReactNode, useState } from "react";

const mocking = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";

// Browser only (ssr: false): the mock API can't run on the server, and this keeps it
// out of the server build entirely.
const MockApi = dynamic(() => import("@/shared/mocks/MockApi").then((m) => m.MockApi), {
  ssr: false,
});

/** App-wide providers: data fetching (TanStack Query) and, when turned on, the mock API. */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  );

  const content = <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return mocking ? <MockApi>{content}</MockApi> : content;
}
