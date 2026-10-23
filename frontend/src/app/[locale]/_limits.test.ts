import { describe, expect, it } from "vitest";
import {
  CHAR_WARN_AT,
  audioFits,
  ENDING_SOON_MS,
  MAX_RECORDING_MS,
  MAX_SESSIONS,
  SESSION_CHAR_LIMIT,
  charState,
  countChars,
  recordingPhase,
  sessionsFull,
  warnAt,
} from "./_limits";

const said = (...texts: string[]) => texts.map((original) => ({ original, translation: "x".repeat(500) }));

describe("length of one recording", () => {
  it("lets a fresh recording simply run", () => {
    expect(recordingPhase(0)).toBe("running");
    expect(recordingPhase(ENDING_SOON_MS - 1)).toBe("running");
  });

  it("warns shortly before the cap", () => {
    expect(recordingPhase(ENDING_SOON_MS)).toBe("endingSoon");
    expect(recordingPhase(MAX_RECORDING_MS - 1)).toBe("endingSoon");
  });

  it("stops at the cap", () => {
    expect(recordingPhase(MAX_RECORDING_MS)).toBe("stop");
    expect(recordingPhase(MAX_RECORDING_MS * 2)).toBe("stop");
  });
});

describe("characters of a conversation", () => {
  it("counts both sides together, but not the translation", () => {
    expect(countChars(said("Hallo", "Guten Tag"))).toBe(14);
  });

  it("counts an empty conversation as zero", () => {
    expect(countChars([])).toBe(0);
  });

  it("reports a clear road below the warning point", () => {
    expect(charState(0)).toBe("ok");
    expect(charState(CHAR_WARN_AT - 1)).toBe("ok");
  });

  it("warns from the warning point on", () => {
    expect(charState(CHAR_WARN_AT)).toBe("near");
    expect(charState(SESSION_CHAR_LIMIT - 1)).toBe("near");
  });

  it("is full at the limit", () => {
    expect(charState(SESSION_CHAR_LIMIT)).toBe("full");
    expect(charState(SESSION_CHAR_LIMIT + 5000)).toBe("full");
  });
});

describe("pool of conversations", () => {
  it("stays quiet while there is room", () => {
    expect(sessionsFull(0)).toBe(false);
    expect(sessionsFull(MAX_SESSIONS - 1)).toBe(false);
  });

  it("warns as soon as the pool is full", () => {
    expect(sessionsFull(MAX_SESSIONS)).toBe(true);
  });

  it("follows the limit of the installation", () => {
    expect(sessionsFull(6, 7)).toBe(false);
    expect(sessionsFull(7, 7)).toBe(true);
  });
});

describe("limit from the installation", () => {
  it("warns and is full at its own limit", () => {
    expect(warnAt(1000)).toBe(900);
    expect(charState(899, 1000)).toBe("ok");
    expect(charState(900, 1000)).toBe("near");
    expect(charState(1000, 1000)).toBe("full");
  });

  it("warns from eighteen thousand at the built-in limit", () => {
    expect(warnAt()).toBe(CHAR_WARN_AT);
    expect(warnAt()).toBe(18_000);
  });
});

describe("size of one recording", () => {
  it("lets everything up to the limit through", () => {
    expect(audioFits(0, 1000)).toBe(true);
    expect(audioFits(1000, 1000)).toBe(true);
  });

  it("refuses what lies above it", () => {
    expect(audioFits(1001, 1000)).toBe(false);
    expect(audioFits(33_000_000, 30 * 1024 * 1024)).toBe(false);
  });
});
