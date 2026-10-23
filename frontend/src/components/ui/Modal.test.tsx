// @vitest-environment jsdom
/** A dialog has a name, keeps the keyboard inside and hands the focus back. */

import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@/testing/render";

import Modal from "./Modal";

afterEach(cleanup);

function tab(shift = false) {
  fireEvent.keyDown(document, { key: "Tab", shiftKey: shift });
}

describe("a dialog", () => {
  it("is announced with its title, not as a nameless dialog", () => {
    render(
      <Modal open onClose={() => {}} title="Past conversations">
        <button type="button">Open</button>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog");
    const labelId = dialog.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)!.textContent).toBe("Past conversations");
  });

  it("takes a name of its own when it has no visible title", () => {
    render(
      <Modal open onClose={() => {}} ariaLabel="Settings">
        <button type="button">Save</button>
      </Modal>,
    );

    expect(screen.getByRole("dialog").getAttribute("aria-label")).toBe("Settings");
  });

  it("moves the focus into itself when it opens", () => {
    render(
      <Modal open onClose={() => {}} title="Past conversations">
        <button type="button">First entry</button>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(document.body);
  });

  it("keeps Tab inside, the page behind must stay out of reach", () => {
    render(
      <>
        <button type="button">Behind the overlay</button>
        <Modal open onClose={() => {}} title="Past conversations">
          <button type="button">First entry</button>
          <button type="button">Second entry</button>
        </Modal>
      </>,
    );

    const first = screen.getByText("First entry");
    const second = screen.getByText("Second entry");
    const close = screen.getByLabelText("Close");

    second.focus();
    tab();
    expect(document.activeElement).toBe(close);
    tab(true);
    expect(document.activeElement).toBe(second);
    close.focus();
    tab(true);
    expect(document.activeElement).toBe(second);
    first.focus();
    expect(document.activeElement).not.toBe(screen.getByText("Behind the overlay"));
  });

  it("gives the focus back to what opened it", () => {
    function Page() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>Past conversations</button>
          <Modal open={open} onClose={() => setOpen(false)} title="Past conversations">
            <button type="button">First entry</button>
          </Modal>
        </>
      );
    }

    render(<Page />);
    const opener = screen.getByText("Past conversations");
    opener.focus();
    fireEvent.click(opener);
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);

    fireEvent.keyDown(document, { key: "Escape" });

    expect(document.activeElement).toBe(opener);
  });

  it("still closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Past conversations">
        <button type="button">First entry</button>
      </Modal>,
    );

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });
});
