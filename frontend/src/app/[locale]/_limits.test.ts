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

describe("Dauer einer Aufnahme", () => {
  it("lässt eine frische Aufnahme einfach laufen", () => {
    expect(recordingPhase(0)).toBe("running");
    expect(recordingPhase(ENDING_SOON_MS - 1)).toBe("running");
  });

  it("warnt kurz vor der Kappe", () => {
    expect(recordingPhase(ENDING_SOON_MS)).toBe("endingSoon");
    expect(recordingPhase(MAX_RECORDING_MS - 1)).toBe("endingSoon");
  });

  it("stoppt an der Kappe", () => {
    expect(recordingPhase(MAX_RECORDING_MS)).toBe("stop");
    expect(recordingPhase(MAX_RECORDING_MS * 2)).toBe("stop");
  });
});

describe("Zeichen eines Gesprächs", () => {
  it("zählt beide Seiten zusammen, die Übersetzung aber nicht", () => {
    expect(countChars(said("Hallo", "Guten Tag"))).toBe(14);
  });

  it("zählt ein leeres Gespräch als null", () => {
    expect(countChars([])).toBe(0);
  });

  it("meldet freie Fahrt unter der Warnschwelle", () => {
    expect(charState(0)).toBe("ok");
    expect(charState(CHAR_WARN_AT - 1)).toBe("ok");
  });

  it("warnt ab der Warnschwelle", () => {
    expect(charState(CHAR_WARN_AT)).toBe("near");
    expect(charState(SESSION_CHAR_LIMIT - 1)).toBe("near");
  });

  it("ist an der Grenze voll", () => {
    expect(charState(SESSION_CHAR_LIMIT)).toBe("full");
    expect(charState(SESSION_CHAR_LIMIT + 5000)).toBe("full");
  });
});

describe("Vorrat an Gesprächen", () => {
  it("schweigt, solange noch Platz ist", () => {
    expect(sessionsFull(0)).toBe(false);
    expect(sessionsFull(MAX_SESSIONS - 1)).toBe(false);
  });

  it("warnt, sobald der Vorrat voll ist", () => {
    expect(sessionsFull(MAX_SESSIONS)).toBe(true);
  });

  it("folgt der Grenze der Installation", () => {
    expect(sessionsFull(6, 7)).toBe(false);
    expect(sessionsFull(7, 7)).toBe(true);
  });
});

describe("Grenze aus der Installation", () => {
  it("warnt und ist voll an der eigenen Grenze", () => {
    expect(warnAt(1000)).toBe(900);
    expect(charState(899, 1000)).toBe("ok");
    expect(charState(900, 1000)).toBe("near");
    expect(charState(1000, 1000)).toBe("full");
  });

  it("warnt bei der eingebauten Grenze ab achtzehntausend", () => {
    expect(warnAt()).toBe(CHAR_WARN_AT);
    expect(warnAt()).toBe(18_000);
  });
});

describe("Groesse einer Aufnahme", () => {
  it("laesst alles bis zur Grenze durch", () => {
    expect(audioFits(0, 1000)).toBe(true);
    expect(audioFits(1000, 1000)).toBe(true);
  });

  it("lehnt ab, was darueber liegt", () => {
    expect(audioFits(1001, 1000)).toBe(false);
    expect(audioFits(33_000_000, 30 * 1024 * 1024)).toBe(false);
  });
});
