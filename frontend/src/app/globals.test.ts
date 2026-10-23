/**
 * Guard over the hand-written classes in globals.css.
 *
 * A class whose definition nobody references is either dead weight or, worse,
 * the other half of a rename that reached the stylesheet and not the component.
 * The styling then simply stays away, with nothing in the build complaining,
 * which is how a renamed tooltip class once lost every one of its users.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(import.meta.dirname, "..", "..");

/** Composed at runtime from the tone, so no file carries the whole name. */
const COMPOSED = [
  "status-mark--brand",
  "status-mark--error",
  "status-mark--muted",
  "status-mark--success",
  "status-mark--warn",
];

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) sourceFiles(path, out);
    else if (/\.tsx?$/.test(name)) out.push(path);
  }
  return out;
}

const css = readFileSync(join(ROOT, "src/app/globals.css"), "utf8");
const code = sourceFiles(join(ROOT, "src")).map((f) => readFileSync(f, "utf8")).join("\n");

describe("globals.css", () => {
  it("defines no class that nothing uses", () => {
    const defined = new Set(
      [...css.matchAll(/(?<![\w-])\.([a-zA-Z][a-zA-Z0-9_-]*)/g)].map((m) => m[1]),
    );
    const orphans = [...defined]
      .filter((name) => !COMPOSED.includes(name))
      .filter((name) => !code.includes(name))
      .sort();
    expect(orphans).toEqual([]);
  });
});
