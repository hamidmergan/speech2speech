/** A stroke left of the word for everything that changes on its own. */

import type { ReactNode } from "react";

/** The tones a status mark can take. */
export type StatusTone = "brand" | "success" | "error" | "warn" | "muted";

export default function StatusMark({
  tone,
  pulse = false,
  className = "",
  children,
}: {
  tone: StatusTone;
  pulse?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={`status-mark status-mark--${tone}${pulse ? " status-mark--pulse" : ""} ${className}`}>
      {children}
    </span>
  );
}
