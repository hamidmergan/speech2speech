"use client";

import { useEffect, useRef, useState } from "react";

import { renameCommit, renameErrorText } from "./renameCommit";

/** Field for renaming in place, a rejected name keeps it open. */
export function InlineRename({
  value, onSave, onCancel, errorText,
}: {
  value: string;
  onSave: (next: string) => Promise<void>;
  onCancel: () => void;
  errorText: string;
}) {
  const [draft, setDraft] = useState(value);
  const [shownError, setShownError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const fieldRef = useRef<HTMLInputElement>(null);
  // Prevents the second save when Enter leaves the field and triggers blur.
  const doneRef = useRef(false);

  useEffect(() => {
    fieldRef.current?.select();
  }, []);

  async function save() {
    if (saving || doneRef.current) return;
    const outcome = renameCommit(draft, value);
    if (outcome.kind === "abort") {
      doneRef.current = true;
      onCancel();
      return;
    }
    setSaving(true);
    try {
      await onSave(outcome.title);
      doneRef.current = true;
      onCancel();
    } catch (e) {
      setShownError(renameErrorText(e, errorText));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
      <input
        ref={fieldRef}
        type="text"
        value={draft}
        disabled={saving}
        autoFocus
        onChange={(e) => { setDraft(e.target.value); setShownError(null); }}
        onBlur={() => { void save(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); void save(); }
          if (e.key === "Escape") { e.preventDefault(); doneRef.current = true; onCancel(); }
        }}
        className="w-full text-sm font-semibold rounded-md px-2 py-1 bg-background outline-none border-2"
        style={{ borderColor: shownError ? "var(--error-border)" : "var(--kb)", color: "var(--foreground)" }}
      />
      {/* Error line in the look that renaming a source already uses. */}
      {shownError && (
        <p className="text-xs mt-1 rounded-md px-2 py-1"
          style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}>
          {shownError}
        </p>
      )}
    </div>
  );
}
