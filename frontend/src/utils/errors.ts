import { ApiError } from "../services/http";

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  const message = error instanceof Error ? error.message : "Unexpected error";
  return new ApiError(0, "unknown", message);
}

/** A sentence the person can act on, for the error shown above a form or a page. */
export function describeError(error: unknown): string {
  const apiError = asApiError(error);
  if (apiError.status === 0 && apiError.code === "network_error") {
    return "Cannot reach the server. Check your connection and try again.";
  }
  if (apiError.status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (apiError.status === 403) {
    return "You do not have access to this.";
  }
  if (apiError.status === 404) {
    return "Not found. It may have been removed, or the link is wrong.";
  }
  if (apiError.status >= 500) {
    return "Something went wrong on the server. Please try again in a moment.";
  }
  return apiError.message;
}

/** Field-level messages of a 422 answer: `{ field: message }`. */
export function fieldErrors(error: unknown): Record<string, string> {
  const apiError = asApiError(error);
  const result: Record<string, string> = {};
  if (apiError.code === "validation_error" && Array.isArray(apiError.details)) {
    for (const item of apiError.details as unknown[]) {
      if (typeof item === "object" && item !== null) {
        const { field, message } = item as { field?: unknown; message?: unknown };
        if (typeof field === "string" && typeof message === "string") {
          result[field] = message;
        }
      }
    }
  }
  return result;
}

/** A client-made id so that a repeated request changes nothing on the server. */
export function newRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    return (char === "x" ? random : (random % 4) + 8).toString(16);
  });
}
