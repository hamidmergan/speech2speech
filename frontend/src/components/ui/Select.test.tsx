// @vitest-environment jsdom
/**
 * The language pill. Its list is rendered into document.body, so only the ARIA
 * ids tie it back to the button a screen reader is standing on.
 */

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@/testing/render";

import Select from "./Select";

// jsdom has no layout, so the list cannot scroll a highlighted entry into view.
beforeAll(() => { Element.prototype.scrollIntoView = () => {}; });
afterEach(cleanup);

const OPTIONS = [
  { value: "DE", label: "German" },
  { value: "EN-US", label: "English" },
  { value: "FR", label: "French" },
] as const;

function open() {
  const button = screen.getByRole("combobox");
  fireEvent.click(button);
  return button;
}

describe("the language picker", () => {
  it("points at the list it opens", () => {
    render(<Select value="DE" onChange={() => {}} options={OPTIONS} ariaLabel="Language" />);
    const button = open();

    const controls = button.getAttribute("aria-controls");
    expect(controls).toBeTruthy();
    const list = document.getElementById(controls!);
    expect(list).not.toBeNull();
    expect(list!.getAttribute("role")).toBe("listbox");
    expect([...list!.querySelectorAll('[role="option"]')].map((o) => o.textContent)).toEqual([
      "German", "English", "French",
    ]);
  });

  it("names the highlighted entry while the arrow keys walk the list", () => {
    render(<Select value="DE" onChange={() => {}} options={OPTIONS} ariaLabel="Language" />);
    const button = open();

    const named = () => {
      const id = button.getAttribute("aria-activedescendant");
      expect(id, "the highlight has to have a name").toBeTruthy();
      return document.getElementById(id!)!.textContent;
    };

    expect(named()).toBe("German");
    fireEvent.keyDown(button, { key: "ArrowDown" });
    expect(named()).toBe("English");
    fireEvent.keyDown(button, { key: "ArrowDown" });
    expect(named()).toBe("French");
    fireEvent.keyDown(button, { key: "ArrowUp" });
    expect(named()).toBe("English");
  });

  it("picks the entry it just named", () => {
    const onChange = vi.fn();
    render(<Select value="DE" onChange={onChange} options={OPTIONS} ariaLabel="Language" />);
    const button = open();

    fireEvent.keyDown(button, { key: "ArrowDown" });
    const named = document.getElementById(button.getAttribute("aria-activedescendant")!)!.textContent;
    fireEvent.keyDown(button, { key: "Enter" });

    expect(named).toBe("English");
    expect(onChange).toHaveBeenCalledWith("EN-US");
  });

  it("names nothing while it is closed", () => {
    render(<Select value="DE" onChange={() => {}} options={OPTIONS} ariaLabel="Language" />);

    expect(screen.getByRole("combobox").getAttribute("aria-activedescendant")).toBeNull();
  });
});
