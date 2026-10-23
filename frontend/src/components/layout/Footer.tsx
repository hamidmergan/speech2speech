"use client";

import { useTranslations } from "next-intl";

/** One quiet band at the bottom. It carries the notice about machine translation. */
export default function Footer() {
  const t = useTranslations("footer");

  return (
    <footer
      className="px-6 pt-8 pb-6 text-base"
      style={{ backgroundColor: "var(--header-bg)", color: "rgba(255,255,255,0.6)", borderTop: "1px solid var(--border)" }}
    >
      <div className="mx-auto w-full max-w-5xl flex flex-col gap-6 text-center">
        <p className="mx-auto max-w-2xl text-xs leading-relaxed">{t("machineNotice")}</p>
        <p className="text-sm">{t("selfHosted")}</p>
      </div>
    </footer>
  );
}
