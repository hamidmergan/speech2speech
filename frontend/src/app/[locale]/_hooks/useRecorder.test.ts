// @vitest-environment jsdom
/**
 * The microphone. Two paths that only exist in this repo: a recording that grew
 * past the ceiling, and an origin the browser hands out no microphone on.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@/testing/render";

import { microphoneReachable, useRecorder, type RecordingSession } from "./useRecorder";

/** Every stop on a recorder that is already inactive, which the browser refuses. */
let illegalStops = 0;
let recorders: FakeRecorder[] = [];

class FakeRecorder {
  state: "recording" | "inactive" = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  static isTypeSupported() { return true; }

  start() { this.state = "recording"; recorders.push(this); }

  stop() {
    if (this.state === "inactive") {
      illegalStops += 1;
      throw new DOMException("already inactive", "InvalidStateError");
    }
    this.state = "inactive";
    this.onstop?.();
  }

  /** One window of audio of this many bytes. */
  emit(bytes: number) {
    this.ondataavailable?.({ data: new Blob([new Uint8Array(bytes)]) });
  }
}

function session(over: Partial<RecordingSession> = {}): RecordingSession {
  return {
    language: "de",
    maxBytes: 100,
    onPartial: vi.fn(),
    onFinal: vi.fn(),
    onQuiet: vi.fn(),
    onEndingSoon: vi.fn(),
    onAutoStop: vi.fn(),
    onError: vi.fn(),
    ...over,
  };
}

beforeEach(() => {
  illegalStops = 0;
  recorders = [];
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }) },
  });
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ text: "" }) })));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("an origin without a microphone", () => {
  it("is not reachable when the browser hides mediaDevices", () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });

    expect(microphoneReachable()).toBe(false);
  });

  it("says so instead of blaming a refused permission", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    const s = session();
    const { result } = renderHook(() => useRecorder());

    await act(async () => { await result.current.start(s); });

    expect(s.onError).toHaveBeenCalledWith("insecure");
    expect(s.onError).not.toHaveBeenCalledWith("mic");
    expect(s.onFinal).toHaveBeenCalledWith("");
  });

  it("still reports a refused permission as one", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: async () => { throw new Error("NotAllowedError"); } },
    });
    const s = session();
    const { result } = renderHook(() => useRecorder());

    await act(async () => { await result.current.start(s); });

    expect(s.onError).toHaveBeenCalledWith("mic");
  });
});

describe("a recording past the ceiling", () => {
  it("ends the recording once and never stops an inactive recorder", async () => {
    const s = session({ maxBytes: 10 });
    const { result } = renderHook(() => useRecorder());
    await act(async () => { await result.current.start(s); });
    const recorder = recorders[0];

    await act(async () => {
      // The oversized window goes out, and a second one is queued behind it
      // before the first has come back.
      recorder.emit(50);
      recorder.emit(50);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(s.onError).toHaveBeenCalledWith("tooLarge");
    expect(s.onAutoStop).toHaveBeenCalledTimes(1);
    expect(illegalStops).toBe(0);
    expect(recorder.state).toBe("inactive");
    // Nothing of the oversized recording was sent to the model.
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(0);
  });
});
