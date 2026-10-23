const API_BASE = "";
const BACKEND_BASE = "/api";

/** Everything that waits for the access password to be entered again. */
type Listener = () => void;
const lockedListeners = new Set<Listener>();

/** The page registers here, so a 401 from any call reopens the password form. */
export function onAccessLocked(listener: Listener): () => void {
  lockedListeners.add(listener);
  return () => lockedListeners.delete(listener);
}

function announceLocked() {
  for (const listener of lockedListeners) listener();
}

const FALLBACKS = {
  de: {
    unknownError: "Unbekannter Fehler",
    // Shown whenever the backend gives no usable detail - never the raw status code.
    genericError: "Da ist etwas schiefgelaufen. Bitte versuche es erneut.",
  },
  en: {
    unknownError: "Unknown error",
    genericError: "Something went wrong. Please try again.",
  },
} as const;

function fallback(key: keyof typeof FALLBACKS["de"]): string {
  return FALLBACKS[readLocaleFromCookie()][key];
}

/** Locale-aware fallback text for spots outside ApiClient that need one, never the raw status code. */
export function genericErrorMessage(): string {
  return fallback("genericError");
}

export function parseDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in (detail as object)) {
    return String((detail as Record<string, unknown>).message);
  }
  return fallback;
}

function _parseErrorResponse(errorBody: { detail?: unknown }, fallbackStatus: number): Error {
  const detail = errorBody.detail;
  // A reached limit carries its sentence in detail.message.
  if (detail && typeof detail === "object" && "message" in (detail as object)) {
    return new Error(String((detail as Record<string, unknown>).message));
  }
  if (typeof detail === "string") return new Error(detail);
  // Validation errors and bodies without a usable detail land here - log the status for debugging,
  // but never put the raw code in front of the user.
  console.error(`API error ${fallbackStatus}:`, detail);
  return new Error(fallback("genericError"));
}

function readLocaleFromCookie(): "de" | "en" {
  if (typeof document === "undefined") return "de";
  const match = document.cookie.match(/(?:^|;\s*)NEXT_LOCALE=(de|en)/);
  return (match?.[1] as "de" | "en") ?? "de";
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async fetch(path: string, options: RequestInit = {}): Promise<Response> {
    const headers = new Headers(options.headers);
    if (!headers.has("Accept-Language")) {
      headers.set("Accept-Language", readLocaleFromCookie());
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      credentials: "include",
      headers,
    });

    // There is no login page. A 401 only means the access password is wanted again,
    // and the page asks for it where it stands.
    if (response.status === 401) announceLocked();

    return response;
  }

  async postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const response = await this.fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }

  async getJson<T>(path: string): Promise<T> {
    const response = await this.fetch(path);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: fallback("unknownError") }));
      throw _parseErrorResponse(error, response.status);
    }

    return response.json();
  }
}

export const api = new ApiClient(API_BASE);
export const backendApi = new ApiClient(BACKEND_BASE);
