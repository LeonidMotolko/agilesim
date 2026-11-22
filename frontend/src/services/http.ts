import { getAuth } from "./authStorage";

/** In development Vite proxies /api to the backend; in production nginx does. */
export const API_BASE = "/api/v1";

/** Fired on window when the server rejects the access token, so the app can sign out. */
export const UNAUTHORIZED_EVENT = "agilesim:unauthorized";

/** An error answer of the API, or a failure to reach it (status 0). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toApiError(status: number, payload: unknown): ApiError {
  const error = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  const code = typeof error?.code === "string" ? error.code : "http_error";
  const message = typeof error?.message === "string" ? error.message : `Request failed (${status})`;
  return new ApiError(status, code, message, error?.details);
}

export interface RequestOptions {
  body?: unknown;
  signal?: AbortSignal;
  /** Send the access token (default). Public endpoints and sign-in turn it off. */
  auth?: boolean;
}

export async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = options.auth === false ? null : (getAuth()?.token ?? null);
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let body: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(0, "network_error", "Cannot reach the server");
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token !== null) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw toApiError(response.status, payload);
  }
  return payload as T;
}
