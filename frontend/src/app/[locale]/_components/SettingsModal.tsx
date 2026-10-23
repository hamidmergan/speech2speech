"use client";

import { useTranslations } from "next-intl";
import { Check, X } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import ToggleRow from "@/components/ui/ToggleRow";

interface Props {
  open: boolean;
  onClose: () => void;
  /** A speech to text model is configured. */
  stt: boolean;
  /** A speech model is configured. */
  tts: boolean;
  /** A chat model is configured. */
  translation: boolean;
  readAloud: boolean;
  onReadAloud: (on: boolean) => void;
  /** A password guards the page, so there is something to sign out of. */
  accessRequired: boolean;
  onLogout: () => void;
}

function Mark({ on }: { on: boolean }) {
  return on
    ? <Check size={14} weight="bold" className="text-success" aria-hidden="true" />
    : <X size={14} weight="bold" className="text-muted-soft" aria-hidden="true" />;
}

/** What this installation can do, and the one switch the page has. */
export default function SettingsModal(p: Props) {
  const t = useTranslations("settings");
  const row = (label: string, on: boolean, missing: string) => (
    <li className="flex items-start gap-2 text-sm">
      <span className="mt-1"><Mark on={on} /></span>
      <span>
        <span className="text-foreground">{label}</span>
        {!on && <span className="block text-xs text-muted">{missing}</span>}
      </span>
    </li>
  );

  return (
    <Modal
      open={p.open}
      onClose={p.onClose}
      title={t("title")}
      size="md"
      footer={
        <>
          {p.accessRequired && (
            <button type="button" onClick={p.onLogout} className="px-4 py-2 text-sm btn-secondary rounded-lg">
              {t("logout")}
            </button>
          )}
          <button type="button" onClick={p.onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {t("close")}
          </button>
        </>
      }
    >
      <p className="text-sm text-muted mb-4">{t("description")}</p>
      <ul className="space-y-2 mb-5">
        {row(t("models.translation"), p.translation, t("models.translationMissing"))}
        {row(t("models.stt"), p.stt, t("models.sttMissing"))}
        {row(t("models.tts"), p.tts, t("models.ttsMissing"))}
      </ul>
      <ToggleRow
        title={t("readAloud")}
        description={p.tts ? t("readAloudHint") : t("models.ttsMissing")}
        checked={p.readAloud && p.tts}
        disabled={!p.tts}
        onToggle={() => p.onReadAloud(!p.readAloud)}
      />
      <p className="mt-4 text-xs text-muted">{t("privacy")}</p>
    </Modal>
  );
}
