"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowCounterClockwise, ClockCounterClockwise, FileText, Gear } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { api, onAccessLocked } from "@/lib/api";
import { useVoicePlayer } from "@/hooks/useVoicePlayer";
import AccessGate from "./_components/AccessGate";
import ConversationView from "./_components/ConversationView";
import ProtocolModal from "./_components/ProtocolModal";
import SavedConversationsModal from "./_components/SavedConversationsModal";
import SettingsModal from "./_components/SettingsModal";
import { createSession, deleteSession, fetchSession, listSessions, patchSession, putTurn, SPEAK_PATH, type SessionSummary } from "./_api";
import { createMirror } from "./_mirror";
import { useConversation } from "./_hooks/useConversation";
import { useInstallation } from "./_hooks/useInstallation";
import { otherLang, otherSide, type LangCode, type Side, type Turn } from "./_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";

export default function InterpreterPage() {
  const t = useTranslations("conversation");
  const locale = useLocale();

  const installation = useInstallation();
  const [locked, setLocked] = useState(false);
  // Any call that comes back with a 401 reopens the password field.
  useEffect(() => onAccessLocked(() => setLocked(true)), []);
  useEffect(() => {
    if (installation.known) setLocked(!installation.authenticated);
  }, [installation.known, installation.authenticated]);

  const [langs, setLangs] = useState<Record<Side, LangCode>>({ left: "DE", right: "EN-US" });
  const [names, setNames] = useState<Record<Side, string>>(() => ({ left: t("speaker.defaultLeft"), right: t("speaker.defaultRight") }));
  const langsRef = useRef(langs);
  langsRef.current = langs;
  const namesRef = useRef(names);
  namesRef.current = names;
  const [protocolOpen, setProtocolOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [readAloud, setReadAloud] = useState(true);
  const [saved, setSaved] = useState<SessionSummary[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);

  // --- the conversation of two people lives on the server --------------------------------------

  const [sessionId, setSessionId] = useState<string | null>(null);
  const running = useRef<string | null>(null);
  const creating = useRef<Promise<string> | null>(null);

  const adopt = useCallback((id: string | null) => {
    running.current = id;
    setSessionId(id);
  }, []);

  /** The server row appears with the first sentence. */
  const ensureSession = useCallback(async (): Promise<string> => {
    if (running.current) return running.current;
    if (!creating.current) {
      creating.current = createSession({
        left_lang: langsRef.current.left,
        right_lang: langsRef.current.right,
        left_name: namesRef.current.left,
        right_name: namesRef.current.right,
      })
        .then((state) => {
          adopt(state.id);
          return state.id;
        })
        .finally(() => {
          creating.current = null;
        });
    }
    return creating.current;
  }, [adopt]);

  const mirror = useMemo(() => createMirror(async (turn: Turn) => putTurn(await ensureSession(), turn)), [ensureSession]);
  const onTurn = useCallback((turn: Turn) => mirror.push(turn), [mirror]);

  const langOf = useCallback((side: Side) => langsRef.current[side], []);
  const active = useConversation({ langOf, charLimit: installation.sessionCharLimit, onTurn });

  // --- reading a translation aloud -------------------------------------------------------------

  const player = useVoicePlayer({ keepCache: true });
  const canSpeak = installation.tts && readAloud;
  const speakTurn = useCallback((turn: Turn) => {
    const text = turn.translation.trim();
    if (!text) return;
    // The translation is in the language of the other card, that is what is voiced.
    const lang = langsRef.current[otherSide(turn.side)];
    // The key carries the text, so a corrected sentence is fetched again instead of replayed.
    void player.playFromApi(`${turn.id}:${text}`, SPEAK_PATH, { text, lang });
  }, [player]);
  const speaking = useMemo(() => ({
    playing: player.playingId?.split(":")[0] ?? null,
    loading: player.loadingId?.split(":")[0] ?? null,
    failed: player.failedId?.split(":")[0] ?? null,
  }), [player.playingId, player.loadingId, player.failedId]);

  // --- what the buttons do --------------------------------------------------------------------

  const formatTime = useCallback(
    (at: number) => new Date(at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }),
    [locale],
  );
  const formatDate = useCallback(
    (iso: string) => new Date(iso).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }),
    [locale],
  );

  const allowSetup = active.turns.length === 0;

  const patchIfRunning = useCallback((meta: Parameters<typeof patchSession>[1]) => {
    if (running.current) void patchSession(running.current, meta).catch(() => {});
  }, []);

  const rename = (side: Side, name: string) => {
    setNames((cur) => ({ ...cur, [side]: name }));
    patchIfRunning(side === "left" ? { left_name: name } : { right_name: name });
  };

  // Only two languages, so a change on one side decides the other side too.
  const changeLanguage = (side: Side, code: LangCode) => {
    if (!allowSetup || langs[side] === code) return;
    const next = { left: side === "left" ? code : otherLang(code), right: side === "right" ? code : otherLang(code) };
    setLangs(next);
    active.flipTexts();
    patchIfRunning({ left_lang: next.left, right_lang: next.right });
  };

  const swap = () => {
    if (!allowSetup) return;
    const nextLangs = { left: langs.right, right: langs.left };
    const nextNames = { left: names.right, right: names.left };
    setLangs(nextLangs);
    setNames(nextNames);
    active.flipSides();
    patchIfRunning({ left_lang: nextLangs.left, right_lang: nextLangs.right, left_name: nextNames.left, right_name: nextNames.right });
  };

  const newConversation = useCallback(() => {
    active.reset();
    mirror.cancel();
    adopt(null);
  }, [adopt, active, mirror]);

  const openSavedList = () => {
    setSavedOpen(true);
    setSavedLoading(true);
    listSessions()
      .then(setSaved)
      .catch(() => setSaved([]))
      .finally(() => setSavedLoading(false));
  };

  const openSaved = async (entry: SessionSummary) => {
    try {
      const state = await fetchSession(entry.id);
      mirror.cancel();
      adopt(state.id);
      active.load(state.turns, state.ended);
      setLangs({ left: state.left_lang, right: state.right_lang });
      setNames({ left: state.left_name || namesRef.current.left, right: state.right_name || namesRef.current.right });
      setSavedOpen(false);
    } catch {
      // The list stays open, the entry could not be loaded.
    }
  };

  const deleteSaved = async (id: string) => {
    try {
      await deleteSession(id);
      setSaved((list) => list.filter((entry) => entry.id !== id));
      if (running.current === id) newConversation();
    } catch {
      // Nothing to do, the entry stays.
    }
  };

  const logout = async () => {
    await api.fetch("/api/access/logout", { method: "POST" }).catch(() => {});
    setSettingsOpen(false);
    setLocked(true);
  };

  if (locked) {
    return (
      <AccessGate
        onOpened={() => {
          setLocked(false);
          installation.reload();
        }}
      />
    );
  }

  return (
    <>
      <div className="max-w-5xl mx-auto px-4 py-8">
        <section>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-10">
            <h1 className="text-xl font-bold">{t("title")}</h1>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => setProtocolOpen(true)} className={ACTION}>
                <FileText size={14} weight="bold" />
                {t("actions.protocol")}
              </button>
              <button type="button" onClick={openSavedList} className={ACTION}>
                <ClockCounterClockwise size={14} weight="bold" />
                {t("actions.saved")}
              </button>
              <button type="button" onClick={newConversation} className={ACTION}>
                <ArrowCounterClockwise size={14} weight="bold" />
                {t("actions.newConversation")}
              </button>
              <IconButton onClick={() => setSettingsOpen(true)} aria-label={t("actions.settings")} title={t("actions.settings")}>
                <Gear size={16} weight="bold" />
              </IconButton>
            </div>
          </div>
          <p className="text-sm text-muted mb-1">{t("intro")}</p>
          <p className="text-sm text-muted mb-5">{t("hint")}</p>

          {installation.known && !installation.translation && (
            <p className="mb-5 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
              {t("noTranslationModel")}
            </p>
          )}
          {installation.known && !installation.stt && (
            <p className="mb-5 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
              {t("noSpeechModel")}
            </p>
          )}

          {active.fill !== "ok" && (
            <p className="mb-5 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
              {t(active.fill === "full" ? "limits.full" : "limits.near")}
            </p>
          )}

          <ConversationView
            turns={active.turns}
            recording={active.recording}
            quiet={active.quiet}
            endingSoon={active.endingSoon}
            floor={active.floor}
            ended={active.ended}
            notice={active.notice}
            langs={langs}
            names={names}
            allowSetup={allowSetup}
            canSpeak={canSpeak}
            speaking={speaking}
            onSpeak={speakTurn}
            onLanguage={changeLanguage}
            onRename={rename}
            onSwap={swap}
            onMic={active.toggleMic}
            onBegin={active.begin}
            onType={active.type}
            onTranslate={active.translateTyped}
            formatTime={formatTime}
          />
        </section>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        stt={installation.stt}
        tts={installation.tts}
        translation={installation.translation}
        readAloud={readAloud}
        onReadAloud={setReadAloud}
        accessRequired={installation.accessRequired}
        onLogout={() => void logout()}
      />
      <ProtocolModal open={protocolOpen} onClose={() => setProtocolOpen(false)} turns={active.turns} names={names} formatTime={formatTime} />
      <SavedConversationsModal
        open={savedOpen}
        onClose={() => setSavedOpen(false)}
        list={saved}
        loading={savedLoading}
        currentId={sessionId}
        maxSessions={installation.maxSessions}
        onOpen={(entry) => void openSaved(entry)}
        onDelete={(id) => void deleteSaved(id)}
        formatDate={formatDate}
      />
    </>
  );
}
