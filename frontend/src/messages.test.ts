/**
 * Guards over the two message catalogues.
 *
 * Both locales have to carry the same keys, and every key a component asks for
 * by name has to be there. A missing key is not loud: next-intl renders the key
 * path, so a rename that misses one call site reaches the page unnoticed.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(import.meta.dirname, "..");

function flatten(value: unknown, prefix = "", into = new Set<string>()): Set<string> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, inner] of Object.entries(value)) {
      flatten(inner, prefix ? `${prefix}.${key}` : key, into);
    }
  } else {
    into.add(prefix);
  }
  return into;
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) sourceFiles(path, out);
    else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) out.push(path);
  }
  return out;
}

const catalogue = (locale: string) =>
  flatten(JSON.parse(readFileSync(join(ROOT, "messages", `${locale}.json`), "utf8")));

const en = catalogue("en");
const de = catalogue("de");

describe("message catalogues", () => {
  it("carry the same keys in both locales", () => {
    expect([...en].filter((key) => !de.has(key))).toEqual([]);
    expect([...de].filter((key) => !en.has(key))).toEqual([]);
  });

  it("answer every key a component asks for by name", () => {
    const missing: string[] = [];
    for (const file of sourceFiles(join(ROOT, "src"))) {
      const code = readFileSync(file, "utf8");
      // One variable can be bound to several namespaces in one file, once per
      // component, so a key counts as found under any of them.
      const spaces = new Map<string, string[]>();
      for (const m of code.matchAll(/(?:const|let)\s+(\w+)\s*=\s*useTranslations\(\s*"([^"]*)"\s*\)/g)) {
        spaces.set(m[1], [...(spaces.get(m[1]) ?? []), m[2]]);
      }
      for (const [name, namespaces] of spaces) {
        // Only calls with a literal key, a computed one cannot be checked here.
        for (const call of code.matchAll(new RegExp(`\\b${name}\\(\\s*"([^"]+)"`, "g"))) {
          const paths = namespaces.map((ns) => (ns ? `${ns}.${call[1]}` : call[1]));
          if (!paths.some((path) => en.has(path) && de.has(path))) {
            missing.push(`${file.slice(ROOT.length + 1)}: ${paths.join(" / ")}`);
          }
        }
      }
    }
    expect(missing).toEqual([]);
  });
});
