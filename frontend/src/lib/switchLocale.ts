import type { Locale } from "@/i18n/routing";

/** next-intl sets the language cookie only after startup, so it is written here first. */
export function rememberLocaleCookie(locale: Locale): void {
  document.cookie = `NEXT_LOCALE=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
}
