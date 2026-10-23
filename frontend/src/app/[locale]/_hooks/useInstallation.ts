"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MAX_SESSIONS, SESSION_CHAR_LIMIT } from "../_limits";

export interface Installation {
  /** A speech to text model is set up, so the microphone buttons work. */
  stt: boolean;
  /** A speech model is set up, so a translation can be read aloud. */
  tts: boolean;
  /** A chat model is set up, so anything can be translated at all. */
  translation: boolean;
  /** A password guards the page. */
  accessRequired: boolean;
  /** This browser already gave the password, or none is wanted. */
  authenticated: boolean;
  maxSessions: number;
  sessionCharLimit: number;
  maxAudioBytes: number;
  /** False until the first answer arrives, so the page does not flash a warning. */
  known: boolean;
}

const UNKNOWN: Installation = {
  stt: true,
  tts: false,
  translation: true,
  accessRequired: false,
  authenticated: true,
  maxSessions: MAX_SESSIONS,
  sessionCharLimit: SESSION_CHAR_LIMIT,
  maxAudioBytes: 30 * 1024 * 1024,
  known: false,
};

interface ConfigBody {
  stt?: boolean;
  tts?: boolean;
  translation?: boolean;
  access_required?: boolean;
  limits?: { max_sessions?: number; session_char_limit?: number; max_audio_bytes?: number };
}

interface AccessBody {
  required?: boolean;
  authenticated?: boolean;
}

/** What this installation can do and where its ceilings sit, straight from the backend. */
export function useInstallation(): Installation & { reload: () => void } {
  const [state, setState] = useState<Installation>(UNKNOWN);

  const reload = useCallback(() => {
    const read = (path: string) => api.fetch(path).then((r) => (r.ok ? r.json() : null));
    Promise.all([read("/api/config"), read("/api/access")])
      .then(([config, access]: [ConfigBody | null, AccessBody | null]) => {
        if (!config) return;
        setState({
          stt: config.stt ?? false,
          tts: config.tts ?? false,
          translation: config.translation ?? false,
          accessRequired: config.access_required ?? false,
          // Without an answer from /access nothing is locked, the first real call then says so.
          authenticated: access?.authenticated ?? true,
          maxSessions: config.limits?.max_sessions ?? MAX_SESSIONS,
          sessionCharLimit: config.limits?.session_char_limit ?? SESSION_CHAR_LIMIT,
          maxAudioBytes: config.limits?.max_audio_bytes ?? UNKNOWN.maxAudioBytes,
          known: true,
        });
      })
      .catch(() => {});
  }, []);

  useEffect(reload, [reload]);

  return { ...state, reload };
}
