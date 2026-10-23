/** Rendering a component in a test needs the same message provider the app has. */

import { NextIntlClientProvider } from "next-intl";
import { render as rtlRender, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import messages from "../../messages/en.json";

function wrap(ui: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  );
}

export function render(ui: ReactElement): RenderResult {
  const view = rtlRender(wrap(ui));
  // Wrapped again, otherwise a second render would drop the provider.
  return { ...view, rerender: (next: ReactNode) => view.rerender(wrap(next)) };
}

// Named one by one on purpose. An `export *` next to the local render would
// re-export testing-library's own render under the same name and quietly win,
// and every component would then be rendered without the messages.
export { act, cleanup, fireEvent, renderHook, screen, waitFor, within } from "@testing-library/react";
