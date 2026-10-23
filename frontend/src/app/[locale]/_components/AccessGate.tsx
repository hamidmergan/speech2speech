"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { api, parseDetail } from "@/lib/api";

/** The password field, shown instead of the conversation while the page is locked. */
export default function AccessGate({ onOpened }: { onOpened: () => void }) {
  const t = useTranslations("access");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.fetch("/api/access/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: value }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(parseDetail((body as { detail?: unknown }).detail, t("wrong")));
        return;
      }
      setValue("");
      onOpened();
    } catch {
      setError(t("offline"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-16">
      <h1 className="text-xl font-bold mb-2">{t("title")}</h1>
      <p className="text-sm text-muted mb-6">{t("intro")}</p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label htmlFor="access-password" className="text-sm font-medium text-foreground-soft">
          {t("label")}
        </label>
        <input
          id="access-password"
          type="password"
          value={value}
          autoFocus
          autoComplete="current-password"
          onChange={(e) => { setValue(e.target.value); setError(null); }}
          className="w-full rounded-md border-2 border-border bg-background px-3 py-2 text-base text-foreground focus:border-kb focus:outline-none"
        />
        {error && (
          <p
            role="alert"
            className="rounded-md px-3 py-2 text-sm"
            style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
          >
            {error}
          </p>
        )}
        <button type="submit" disabled={!value || busy} className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50">
          {t("submit")}
        </button>
      </form>
    </div>
  );
}
