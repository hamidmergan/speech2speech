"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { transcribeWindow } from "../_api";
import { audioFits, recordingPhase } from "../_limits";
import { createVoiceMeter, type VoiceMeter } from "../_voiceActivity";

export type RecorderError = "mic" | "insecure" | "stt" | "tooLarge";

/** The browser only exposes the microphone on https or on localhost. */
export function microphoneReachable(): boolean {
  if (typeof navigator === "undefined") return false;
  return typeof navigator.mediaDevices?.getUserMedia === "function";
}

export interface RecordingSession {
  /** The language spoken into this microphone, so the model does not have to guess it. */
  language: string;
  /** Largest recording one request may carry, from the installation. */
  maxBytes: number;
  /** The transcript of everything recorded so far, a few seconds behind the voice. */
  onPartial: (text: string) => void;
  /** The transcript of the whole recording, empty when nothing was understood. */
  onFinal: (text: string) => void;
  /** Nothing is coming in from the microphone right now. */
  onQuiet: (quiet: boolean) => void;
  /** The recording is running into its time limit and will stop in a moment. */
  onEndingSoon: () => void;
  /** The recording gave up after a long silence or at its time limit, as if Done had been pressed. */
  onAutoStop: () => void;
  onError: (kind: RecorderError) => void;
}

interface Handle {
  stop: () => void;
  cancel: () => void;
}

const WINDOW_MS = 4000;
/** After this much silence the status line says that nothing is coming in. */
const QUIET_HINT_MS = 8000;
/** After this much silence the recording stops by itself. */
const SILENCE_STOP_MS = 30000;
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

/** A recording too large for one request. Thrown instead of being sent and refused. */
class TooLarge extends Error {}

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_TYPES.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/**
 * One recording: the whole audio so far goes out every few seconds so the transcript grows
 * while the person is still talking. One window at a time, the final request after the stop
 * goes out at once, even beside a window that is still on its way, and from then on only the
 * final answer counts. A stopped recording finishes on its own while a new one may already
 * start, that is how the other side takes over the word.
 *
 * A window without a voice never leaves the device, and after half a minute of silence the
 * recording stops itself. Heard nothing at all, the model is not asked either, it would invent
 * a sentence out of the silence. A recording also stops at its time limit, because every
 * window resends the whole audio and a long one therefore gets slower with every second.
 */
function record(stream: MediaStream, session: RecordingSession): Handle {
  const mime = pickMime();
  const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  const filename = mime.includes("mp4") ? "window.mp4" : "window.webm";
  const chunks: Blob[] = [];
  const meter: VoiceMeter | null = createVoiceMeter(stream);
  let quiet = false;
  let windowInFlight = false;
  let dirty = false;
  let finalRequested = false;
  let cancelled = false;
  let warned = false;
  const startedAt = Date.now();

  const release = () => {
    meter?.close();
    stream.getTracks().forEach((track) => track.stop());
  };

  const transcribe = async () => {
    const blob = new Blob(chunks, mime ? { type: mime } : undefined);
    // A recording past the ceiling never leaves the device. The server would refuse
    // it too, but only after the whole upload, and that reads as a hang.
    if (!audioFits(blob.size, session.maxBytes)) throw new TooLarge();
    return blob.size > 0 ? transcribeWindow(blob, filename, session.language) : "";
  };

  const sendWindow = async () => {
    if (windowInFlight || finalRequested) {
      dirty = true;
      return;
    }
    windowInFlight = true;
    dirty = false;
    try {
      const text = await transcribe();
      if (!cancelled && !finalRequested) session.onPartial(text);
    } catch (e) {
      if (!cancelled && !finalRequested) {
        if (e instanceof TooLarge) {
          // Nothing more can be sent, so the recording ends here and says why.
          // finalRequested first: the finally below would otherwise fire the
          // queued window, throw TooLarge again and stop an inactive recorder,
          // which throws InvalidStateError as an unhandled rejection.
          finalRequested = true;
          session.onError("tooLarge");
          session.onAutoStop();
          if (recorder.state !== "inactive") recorder.stop();
          return;
        }
        session.onError("stt");
      }
    } finally {
      windowInFlight = false;
      if (!cancelled && !finalRequested && dirty) void sendWindow();
    }
  };

  const sendFinal = async () => {
    finalRequested = true;
    // Nobody said anything, so there is nothing to recognise.
    if (meter && !meter.everHeard()) {
      if (!cancelled) session.onFinal("");
      return;
    }
    try {
      const text = await transcribe();
      if (!cancelled) session.onFinal(text);
    } catch (e) {
      if (cancelled) return;
      session.onError(e instanceof TooLarge ? "tooLarge" : "stt");
      session.onFinal("");
    }
  };

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
    if (recorder.state !== "recording") return;
    if (!meter) {
      void sendWindow();
    } else {
      if (meter.takeHeard()) void sendWindow();
      const silence = meter.quietMs();
      const nowQuiet = silence >= QUIET_HINT_MS;
      if (nowQuiet !== quiet) {
        quiet = nowQuiet;
        session.onQuiet(quiet);
      }
      if (silence >= SILENCE_STOP_MS) {
        session.onAutoStop();
        recorder.stop();
        return;
      }
    }
    const phase = recordingPhase(Date.now() - startedAt);
    if (phase === "endingSoon" && !warned) {
      warned = true;
      session.onEndingSoon();
    }
    if (phase === "stop") {
      session.onAutoStop();
      recorder.stop();
    }
  };
  recorder.onstop = () => {
    release();
    if (!cancelled) void sendFinal();
  };
  recorder.start(WINDOW_MS);

  return {
    stop: () => {
      if (recorder.state !== "inactive") recorder.stop();
    },
    cancel: () => {
      cancelled = true;
      if (recorder.state !== "inactive") recorder.stop();
      release();
    },
  };
}

/** The microphone of this device, one recording at a time. */
export function useRecorder() {
  const current = useRef<Handle | null>(null);
  const starting = useRef(0);

  const start = useCallback(async (session: RecordingSession) => {
    current.current?.stop();
    current.current = null;
    const attempt = (starting.current += 1);
    let stream: MediaStream;
    // Outside a secure origin navigator.mediaDevices is undefined. Reading it
    // inside the try would throw and read as a refused permission.
    if (!microphoneReachable()) {
      session.onError("insecure");
      session.onFinal("");
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      session.onError("mic");
      session.onFinal("");
      return;
    }
    if (attempt !== starting.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    current.current = record(stream, session);
  }, []);

  const stop = useCallback(() => {
    starting.current += 1;
    current.current?.stop();
    current.current = null;
  }, []);

  const cancel = useCallback(() => {
    starting.current += 1;
    current.current?.cancel();
    current.current = null;
  }, []);

  useEffect(() => cancel, [cancel]);

  // One stable object, the hooks above hang their effects on it.
  return useMemo(() => ({ start, stop, cancel }), [start, stop, cancel]);
}
