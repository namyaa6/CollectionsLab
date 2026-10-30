import { useCallback, useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: unknown;
  reload: () => void;
}

/**
 * Runs `fetcher` when the component mounts and again whenever `key` changes.
 * The AbortController cancels a request that is still in flight if the component goes away
 * (or the key changes), so a slow old response can never overwrite a newer one.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetcher(controller.signal)
      .then((result) => setData(result))
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setError(e);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort(); // cleanup: runs before the next effect and on unmount
    // fetcher is a new function every render, so it is left out on purpose:
    // key + attempt are what decide a refetch.
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((a) => a + 1), []);
  return { data, loading, error, reload };
}
