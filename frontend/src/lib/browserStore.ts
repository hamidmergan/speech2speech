/**
 * Everything the app keeps in localStorage, bundled into one key:
 *
 * - `speech2speech.prefs`  device-wide settings, kept for good
 *
 * Every access is wrapped, private mode or a full quota just means nothing is remembered.
 */

export type Theme = "light" | "dark";

export interface Prefs {
  theme?: Theme;
}

export const PREFS_KEY = "speech2speech.prefs";

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage;
  } catch {
    return null;
  }
}

function readJson<T extends object>(key: string): T {
  const s = storage();
  if (!s) return {} as T;
  try {
    const parsed = JSON.parse(s.getItem(key) ?? "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as T) : ({} as T);
  } catch {
    return {} as T;
  }
}

function writeJson(key: string, value: object) {
  const s = storage();
  if (!s) return;
  try {
    if (Object.keys(value).length === 0) s.removeItem(key);
    else s.setItem(key, JSON.stringify(value));
  } catch {
    /* quota or blocked storage */
  }
}

export function readPrefs(): Prefs {
  return readJson<Prefs>(PREFS_KEY);
}

export function updatePrefs(patch: Partial<Prefs>) {
  const next: Prefs = { ...readPrefs(), ...patch };
  for (const k of Object.keys(next) as (keyof Prefs)[]) {
    if (next[k] === undefined) delete next[k];
  }
  writeJson(PREFS_KEY, next);
}
