"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

/** How many generated files the cache holds before the oldest one is released. */
export const CACHE_LIMIT = 20;

interface Options {
  /** Keep what was generated, so a sentence read twice is fetched once. */
  keepCache?: boolean;
  /** How many files the cache holds at most. */
  cacheLimit?: number;
}

/**
 * One audio file at a time.
 *
 * With keepCache the generated files stay, but never more than cacheLimit of
 * them. A long conversation with every sentence read aloud, and every
 * correction of one, would otherwise pin hundreds of blobs in the tab.
 */
export function useVoicePlayer({ keepCache = false, cacheLimit = CACHE_LIMIT }: Options = {}) {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  // The id of the last failure, old callers do not read the field.
  const [failedId, setFailedId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const cacheRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const cache = cacheRef.current;
    return () => {
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      cache.forEach((url) => URL.revokeObjectURL(url));
      cache.clear();
    };
  }, []);

  const stopCurrent = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    // Release here too, because stopping midway fires no event.
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback((key: string, url: string, cached: boolean) => {
    const audio = new Audio(url);
    audioRef.current = audio;
    if (!cached) objectUrlRef.current = url;
    setLoadingId(null);
    setPlayingId(key);
    audio.play().catch(() => {});
    const done = () => {
      setPlayingId(null);
      if (!cached) {
        URL.revokeObjectURL(url);
        objectUrlRef.current = null;
      }
    };
    audio.onended = done;
    audio.onerror = done;
  }, []);

  /** `key` identifies what is playing and keys the cache, `body` is what the endpoint is asked with. */
  const playFromApi = useCallback(async (voiceId: string, endpoint: string, body?: unknown) => {
    stopCurrent();
    // A new attempt clears every old failure.
    setFailedId(null);
    if (playingId === voiceId || loadingId === voiceId) {
      setPlayingId(null);
      setLoadingId(null);
      return;
    }

    const cached = keepCache ? cacheRef.current.get(voiceId) : undefined;
    if (cached) {
      // Youngest again, so the cap drops what has not been played for longest.
      cacheRef.current.delete(voiceId);
      cacheRef.current.set(voiceId, cached);
      start(voiceId, cached, true);
      return;
    }

    setLoadingId(voiceId);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      // Through the client, so a 401 reopens the password field the way every
      // other call does instead of showing a crossed out speaker icon.
      const res = await api.fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? { voice_id: voiceId }),
        signal: controller.signal,
      });
      if (!res.ok) { setLoadingId(null); setFailedId(voiceId); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (keepCache) {
        cacheRef.current.set(voiceId, url);
        while (cacheRef.current.size > cacheLimit) {
          const oldest = cacheRef.current.keys().next().value as string;
          const stale = cacheRef.current.get(oldest);
          cacheRef.current.delete(oldest);
          if (stale) URL.revokeObjectURL(stale);
        }
      }
      start(voiceId, url, keepCache);
    } catch (e) {
      // A cancellation by the user is not an error.
      if ((e as Error).name !== "AbortError") { setLoadingId(null); setFailedId(voiceId); }
    }
  }, [playingId, loadingId, stopCurrent, keepCache, cacheLimit, start]);

  return { playingId, loadingId, failedId, playFromApi };
}
