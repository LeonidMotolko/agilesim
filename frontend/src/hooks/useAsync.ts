import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiError } from "../services/http";
import { asApiError } from "../utils/errors";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  /** True during the first load and after a visible reload, not during silent polling. */
  loading: boolean;
  /** Starts a quiet reload; the promise settles when it has finished (it never rejects). */
  reload: () => Promise<void>;
}

interface Options {
  /** Reload quietly (no loading state) every this many milliseconds. */
  pollMs?: number;
}

/**
 * Runs `load` when the component mounts and when `load` changes (wrap it in useCallback), and
 * keeps the loading and error state next to the data so pages need no boilerplate.
 */
export function useAsync<T>(
  load: (signal: AbortSignal) => Promise<T>,
  options: Options = {},
): AsyncState<T> {
  const { pollMs } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const silent = useRef(false);
  const waiters = useRef<(() => void)[]>([]);

  const settle = useCallback(() => {
    waiters.current.splice(0).forEach((resolve) => resolve());
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (!silent.current) {
      setLoading(true);
    }
    silent.current = false;
    load(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setError(null);
          setLoading(false);
          settle();
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(asApiError(caught));
          setLoading(false);
          settle();
        }
      });
    return () => controller.abort();
  }, [load, tick, settle]);

  // Nobody keeps waiting for a reload after the page is gone.
  useEffect(() => settle, [settle]);

  useEffect(() => {
    if (pollMs === undefined) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      silent.current = true;
      setTick((value) => value + 1);
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs]);

  const reload = useCallback(() => {
    silent.current = true;
    const finished = new Promise<void>((resolve) => {
      waiters.current.push(resolve);
    });
    setTick((value) => value + 1);
    return finished;
  }, []);

  return { data, error, loading, reload };
}
