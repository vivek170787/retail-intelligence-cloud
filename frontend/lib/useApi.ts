"use client";

/**
 * Tiny fetch hook: loading/error/data state plus a refetch handle, used
 * instead of pulling in TanStack Query/SWR for this read-only surface.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState(0);

  const refetch = useCallback(() => setRequestId((id) => id + 1), []);

  useEffect(() => {
    let cancelled = false;

    // Reset via a microtask rather than synchronously in the effect body,
    // so a fresh fetch always shows loading/clears the previous error even
    // though `fetcher` itself is already async.
    Promise.resolve().then(() => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
    });

    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "An unexpected error occurred.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId, ...deps]);

  return { data, loading, error, refetch };
}
