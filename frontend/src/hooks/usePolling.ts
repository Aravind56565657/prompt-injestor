import { useEffect, useRef, useState } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  shouldContinue: (data: T) => boolean,
): { data: T | null; error: Error | null; loading: boolean; refresh: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refresh = async () => {
    try {
      setError(null);
      setData(await fetcherRef.current());
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    let cancelled = false;

    const run = async () => {
      try {
        setError(null);
        const result = await fetcherRef.current();
        if (!active) return;
        setData(result);
        if (shouldContinue(result) && !cancelled) {
          window.setTimeout(run, intervalMs);
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        if (!cancelled) {
          window.setTimeout(run, intervalMs);
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void run();
    return () => {
      active = false;
      cancelled = true;
    };
  }, [intervalMs, shouldContinue]);

  return { data, error, loading, refresh };
}