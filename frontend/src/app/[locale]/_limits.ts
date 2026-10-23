/**
 * The three ceilings of the interpreter: how long one recording may run, how much a
 * conversation may collect and how many conversations are kept. All of them are plain
 * numbers here so they can be tested without a microphone and stay in one place.
 *
 * Two of them are settings of the installation, so the backend reports its own values
 * under GET /config and the page hands them in. The numbers below are the defaults,
 * and they are what the backend uses when nothing is set.
 */

/** A recording stops itself here, every window resends the whole audio so far. */
export const MAX_RECORDING_MS = 300_000;
/** From here the card says that the recording is about to end. */
export const ENDING_SOON_MS = 270_000;

export type RecordingPhase = "running" | "endingSoon" | "stop";

export function recordingPhase(elapsedMs: number): RecordingPhase {
  if (elapsedMs >= MAX_RECORDING_MS) return "stop";
  if (elapsedMs >= ENDING_SOON_MS) return "endingSoon";
  return "running";
}

/** A conversation ends by itself here, roughly an hour of real back and forth. */
export const SESSION_CHAR_LIMIT = 20_000;
/** From which share of the ceiling the page warns that the conversation is nearly full. */
export const WARN_SHARE = 0.9;
/** From here the page warns, at the default ceiling. */
export const CHAR_WARN_AT = SESSION_CHAR_LIMIT * WARN_SHARE;

export type CharState = "ok" | "near" | "full";

/** What was said and typed on both sides, the translation does not count against anyone. */
export function countChars(turns: readonly { original: string }[]): number {
  return turns.reduce((sum, turn) => sum + turn.original.length, 0);
}

export function warnAt(limit: number = SESSION_CHAR_LIMIT): number {
  return Math.floor(limit * WARN_SHARE);
}

export function charState(chars: number, limit: number = SESSION_CHAR_LIMIT): CharState {
  if (chars >= limit) return "full";
  if (chars >= warnAt(limit)) return "near";
  return "ok";
}

/** How many conversations stay, the one untouched longest drops out. */
export const MAX_SESSIONS = 100;

/** True once the next new conversation pushes the last entry of the list out. */
export function sessionsFull(count: number, max: number = MAX_SESSIONS): boolean {
  return count >= max;
}
