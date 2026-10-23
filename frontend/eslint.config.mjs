import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

export default [
  { ignores: [".next/**", ".next-prod/**", "node_modules/**", "public/**"] },
  // The two Next presets, loaded through the compat layer because they are still
  // legacy configs.
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // The viewer and the mind map talk to libraries without useful types, so a
      // hand-written `any` there is a decision, not an oversight.
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
];
