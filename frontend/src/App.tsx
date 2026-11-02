import { useEffect, useState } from "react";

type ApiStatus = "checking" | "online" | "offline";

export function App() {
  const [status, setStatus] = useState<ApiStatus>("checking");

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
    <main>
      <h1>AgileSim</h1>
      <p>
        API status: <strong data-testid="api-status">{status}</strong>
      </p>
    </main>
  );
}
