import { afterEach, describe, expect, it, vi } from "vitest";
import { PREFS_KEY, readPrefs, updatePrefs } from "./browserStore";

// A localStorage stub backed by a plain map, returned so tests can look inside.
function stubStorage(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  vi.stubGlobal("window", {});
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => { store.set(key, value); },
    removeItem: (key: string) => { store.delete(key); },
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() { return store.size; },
  });
  return store;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("prefs", () => {
  it("merges patches and drops undefined fields", () => {
    const store = stubStorage();
    updatePrefs({ theme: "dark" });
    updatePrefs({ theme: undefined });
    expect(readPrefs()).toEqual({});
    expect([...store.keys()]).toEqual([]);
  });

  it("keeps a value a later patch does not touch", () => {
    stubStorage();
    updatePrefs({ theme: "dark" });
    updatePrefs({});
    expect(readPrefs()).toEqual({ theme: "dark" });
  });

  it("reads broken JSON as empty", () => {
    stubStorage({ [PREFS_KEY]: "{broken" });
    expect(readPrefs()).toEqual({});
  });

  it("is empty outside the browser", () => {
    expect(readPrefs()).toEqual({});
  });
});
