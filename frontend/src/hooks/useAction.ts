import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Runs one user action (a button press, a form submit) and tracks `busy` and its error.
 * `onError` is called with every failure, for pages that show errors as floating messages.
 */
export function useAction(onError?: (error: unknown) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const handler = useRef(onError);

  useEffect(() => {
    handler.current = onError;
  }, [onError]);

  const run = useCallback(async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (caught) {
      setError(caught);
      handler.current?.(caught);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { busy, error, run, clearError };
}
