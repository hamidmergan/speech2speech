"use client";

import { useTranslations } from "next-intl";
import { Moon, Sun } from "@phosphor-icons/react";
import HeaderPublicControls from "@/components/layout/HeaderPublicControls";
import { useTheme } from "@/hooks/useTheme";

/** One band at the top: the name of the app, the language and the light switch. */
export default function Header() {
  const t = useTranslations("header");
  const { theme, toggle } = useTheme();

  return (
    <header style={{ backgroundColor: "var(--header-bg)", borderBottom: "1px solid var(--border)" }} className="py-3">
      <div className="px-4 sm:px-6 flex items-center justify-between">
        {/* The page title is the h1, the wordmark is only a name. */}
        <span className="flex items-center text-lg font-semibold tracking-tight text-on-accent">
          {t("productName")}
        </span>
        <div className="flex items-center gap-1.5">
          <HeaderPublicControls />
          <button
            type="button"
            onClick={toggle}
            aria-label={t(theme === "dark" ? "lightMode" : "darkMode")}
            title={t(theme === "dark" ? "lightMode" : "darkMode")}
            className="flex items-center justify-center h-9 w-9 rounded-full btn-on-dark"
          >
            {theme === "dark" ? <Sun size={17} weight="bold" /> : <Moon size={17} weight="bold" />}
          </button>
        </div>
      </div>
    </header>
  );
}
