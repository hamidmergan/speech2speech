/** The three cases of renaming as testable logic next to the field. */

export type RenameAction =
  /** Nothing to do, simply close the field, not an error but a cancel. */
  | { kind: "abort" }
  /** Save with exactly this name. */
  | { kind: "save"; title: string };

/** Empty or unchanged cancels, otherwise it saves. */
export function renameCommit(draft: string, current: string): RenameAction {
  const naechster = draft.trim();
  if (!naechster || naechster === current.trim()) return { kind: "abort" };
  return { kind: "save", title: naechster };
}

/** The reason from the server takes precedence, otherwise the general sentence appears. */
export function renameErrorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
