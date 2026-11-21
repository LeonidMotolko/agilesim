import { useEffect, useState } from "react";

type Status = "checking" | "online" | "offline";

/** Small footer badge: is the backend reachable? */
export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/health", { signal: controller.signal })
      .then((response) => setStatus(response.ok ? "online" : "offline"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setStatus("offline");
        }
      });

    return () => controller.abort();
  }, []);

  return (
    <p className="api-status">
      API status: <strong data-testid="api-status">{status}</strong>
    </p>
  );
}
