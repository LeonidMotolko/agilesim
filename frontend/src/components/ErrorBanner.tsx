import { describeError } from "../utils/errors";

export function ErrorBanner({ error }: { error: unknown }) {
  if (error === null || error === undefined || error === "") {
    return null;
  }
  const message = typeof error === "string" ? error : describeError(error);
  return (
    <div className="banner banner-error" role="alert">
      {message}
    </div>
  );
}
