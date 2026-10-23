import { describe, expect, it } from "vitest";

import { backdropClose, newBackdropPress } from "./backdropClose";

/** An event as React delivers it: what was pressed and where the handle sits. */
function event(target: unknown, currentTarget: unknown) {
  return { target, currentTarget } as never;
}

const BACKDROP = { name: "backdrop" };
const FIELD = { name: "input field" };

describe("backdropClose", () => {
  it("closes on a click on the backdrop", () => {
    let closed = false;
    const h = backdropClose(newBackdropPress(), () => { closed = true; });
    h.onMouseDown(event(BACKDROP, BACKDROP));
    h.onClick(event(BACKDROP, BACKDROP));
    expect(closed).toBe(true);
  });

  it("stays open when a selection began in a field and ended beside it", () => {
    // Exactly the annoying case: the click lands on the shared parent.
    let closed = false;
    const h = backdropClose(newBackdropPress(), () => { closed = true; });
    h.onMouseDown(event(FIELD, BACKDROP));
    h.onClick(event(BACKDROP, BACKDROP));
    expect(closed).toBe(false);
  });

  it("stays open when the click lands on the content", () => {
    let closed = false;
    const h = backdropClose(newBackdropPress(), () => { closed = true; });
    h.onMouseDown(event(FIELD, BACKDROP));
    h.onClick(event(FIELD, BACKDROP));
    expect(closed).toBe(false);
  });

  it("does not forget the previous grab until the next press", () => {
    // After a selection a real click outside has to close again.
    let closed = 0;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { closed += 1; });
    h.onMouseDown(event(FIELD, BACKDROP));
    h.onClick(event(BACKDROP, BACKDROP));
    h.onMouseDown(event(BACKDROP, BACKDROP));
    h.onClick(event(BACKDROP, BACKDROP));
    expect(closed).toBe(1);
  });

  it("does not close while it is switched off", () => {
    // For dialogs that must not go away while saving.
    let closed = false;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { closed = true; }, false);
    h.onMouseDown(event(BACKDROP, BACKDROP));
    h.onClick(event(BACKDROP, BACKDROP));
    expect(closed).toBe(false);
  });
});
