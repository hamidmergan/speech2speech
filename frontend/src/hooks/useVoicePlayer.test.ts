// @vitest-environment jsdom
/** Reading aloud: what the cache keeps, and what a 401 does. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@/testing/render";

import { onAccessLocked } from "@/lib/api";
import { useVoicePlayer } from "./useVoicePlayer";

const SPEAK = "/api/interpreter/speak";

let created: string[] = [];
let revoked: string[] = [];
let answer: { ok: boolean; status: number };

beforeEach(() => {
  created = [];
  revoked = [];
  answer = { ok: true, status: 200 };
  let n = 0;
  URL.createObjectURL = () => {
    const url = `blob:voice-${(n += 1)}`;
    created.push(url);
    return url;
  };
  URL.revokeObjectURL = (url: string) => { revoked.push(url); };
  // jsdom has no audio device, so play resolves and nothing else happens.
  window.HTMLMediaElement.prototype.play = () => Promise.resolve();
  window.HTMLMediaElement.prototype.pause = () => {};
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: answer.ok,
    status: answer.status,
    blob: async () => new Blob(["audio"], { type: "audio/mpeg" }),
    json: async () => ({}),
  })));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function play(player: ReturnType<typeof useVoicePlayer>, key: string) {
  await act(async () => {
    await player.playFromApi(key, SPEAK, { text: key, lang: "EN-US" });
  });
}

describe("the cache of generated speech", () => {
  it("releases the oldest file once it is full, instead of growing forever", async () => {
    const { result } = renderHook(() => useVoicePlayer({ keepCache: true, cacheLimit: 3 }));

    for (const key of ["a", "b", "c", "d", "e"]) {
      await play(result.current, key);
    }

    expect(created.length).toBe(5);
    // Two files beyond the cap, and exactly those two are released again.
    expect(revoked).toEqual([created[0], created[1]]);
  });

  it("asks the server once for a sentence it already holds", async () => {
    const { result } = renderHook(() => useVoicePlayer({ keepCache: true, cacheLimit: 3 }));

    await play(result.current, "a");
    // Playing the same sentence twice in a row stops it, so one other goes between.
    await play(result.current, "b");
    await play(result.current, "a");

    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(2);
    expect(created.length).toBe(2);
  });
});

describe("a 401 on reading aloud", () => {
  it("reopens the password field, the way every other call does", async () => {
    const locked = vi.fn();
    const stop = onAccessLocked(locked);
    answer = { ok: false, status: 401 };
    const { result } = renderHook(() => useVoicePlayer({ keepCache: true }));

    await play(result.current, "a");

    await waitFor(() => expect(locked).toHaveBeenCalled());
    stop();
  });

  it("still marks the sentence as failed", async () => {
    answer = { ok: false, status: 502 };
    const { result } = renderHook(() => useVoicePlayer({ keepCache: true }));

    await play(result.current, "a");

    await waitFor(() => expect(result.current.failedId).toBe("a"));
  });
});
