import { getTranslations } from "next-intl/server";

/** The one page of this app, the conversation itself. */
export default async function HomePage() {
  const t = await getTranslations("layoutMeta");
  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-xl font-bold">{t("title")}</h1>
    </div>
  );
}
