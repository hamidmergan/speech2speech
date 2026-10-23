import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { cookies } from "next/headers";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { setRequestLocale, getMessages, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import "../globals.css";
import Footer from "@/components/layout/Footer";
import Header from "@/components/layout/Header";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "layoutMeta" });
  return {
    title: t("title"),
    description: t("description"),
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

// Render dynamically, the theme comes from a cookie that is read per request.
export const dynamic = "force-dynamic";

// Backfills the theme cookie so the server reads it on the next request.
const themeBootScript = `(function(){try{var t;try{t=JSON.parse(localStorage.getItem('speech2speech.prefs')||'{}').theme;}catch(e){}var hasCookie=document.cookie.indexOf('speech2speech-theme=')!==-1;if(t==='dark'){document.documentElement.setAttribute('data-theme','dark');if(!hasCookie)document.cookie='speech2speech-theme=dark; path=/; max-age=31536000; SameSite=Lax';}else if(t==='light'&&!hasCookie){document.cookie='speech2speech-theme=light; path=/; max-age=31536000; SameSite=Lax';}}catch(e){}})();`;

type Props = {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
};

export default async function RootLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();
  const cookieStore = await cookies();
  const themeCookie = cookieStore.get("speech2speech-theme")?.value;
  const dataTheme = themeCookie === "dark" ? "dark" : undefined;

  return (
    <html lang={locale} data-theme={dataTheme} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geist.variable} min-h-dvh flex flex-col`} suppressHydrationWarning>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
