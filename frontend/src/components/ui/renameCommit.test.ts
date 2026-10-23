/** Empty, unchanged or really new, only the last case may save. */
import { describe, expect, it } from "vitest";

import { renameCommit, renameErrorText } from "./renameCommit";

describe("renameCommit", () => {
  it("saves a name that really is new", () => {
    expect(renameCommit("A new name", "The old name")).toEqual({
      kind: "save",
      title: "A new name",
    });
  });

  it("trims before saving", () => {
    expect(renameCommit("  A new name  ", "The old name")).toEqual({
      kind: "save",
      title: "A new name",
    });
  });

  it("cancels on empty input", () => {
    expect(renameCommit("", "The old name")).toEqual({ kind: "abort" });
  });

  it("cancels on nothing but spaces", () => {
    expect(renameCommit("   ", "The old name")).toEqual({ kind: "abort" });
  });

  it("cancels when the name is unchanged", () => {
    expect(renameCommit("The old name", "The old name")).toEqual({ kind: "abort" });
  });

  it("sees unchanged even with spaces around it", () => {
    expect(renameCommit("  The old name  ", "The old name")).toEqual({ kind: "abort" });
  });
});

describe("renameErrorText", () => {
  it("takes the reason from the server", () => {
    expect(renameErrorText(new Error("The name must not be empty"), "Something went wrong"))
      .toBe("The name must not be empty");
  });

  it("falls back to the general sentence without a reason", () => {
    expect(renameErrorText(new Error(""), "Something went wrong")).toBe("Something went wrong");
    expect(renameErrorText("not an error object", "Something went wrong")).toBe("Something went wrong");
    expect(renameErrorText(undefined, "Something went wrong")).toBe("Something went wrong");
  });
});
