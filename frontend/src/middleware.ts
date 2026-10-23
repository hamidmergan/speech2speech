import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Match all pathnames except for backend rewrites, internals, and static files.
  matcher: [
    "/((?!api|health|_next|_vercel|.*\\..*).*)",
  ],
};
