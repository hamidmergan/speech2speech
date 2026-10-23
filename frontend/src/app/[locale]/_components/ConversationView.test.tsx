// @vitest-environment jsdom
/**
 * The card the other person reads from. Everything asserted here is read back
 * out of the rendered page, not out of the props that were handed in.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@/testing/render";

import ConversationView from "./ConversationView";
import type { Side, Turn } from "../_types";

afterEach(cleanup);

const BASE = {
  turns: [] as Turn[],
  canSpeak: false,
  speaking: { playing: null, loading: null, failed: null },
  onSpeak: vi.fn(),
  recording: null as Side | null,
  quiet: false,
  endingSoon: false,
  floor: null,
  ended: false,
  notice: null,
  langs: { left: "DE", right: "EN-US" } as const,
  names: { left: "Ada", right: "Bo" },
  allowSetup: true,
  stt: true,
  secureContext: true,
  onLanguage: vi.fn(),
  onRename: vi.fn(),
  onSwap: vi.fn(),
  onMic: vi.fn(),
  onBegin: vi.fn(),
  onType: vi.fn(),
  onTranslate: vi.fn(),
  formatTime: () => "12:00",
};

function turn(over: Partial<Turn> = {}): Turn {
  return {
    id: "t1",
    side: "left",
    source: "spoken",
    original: "Guten Tag",
    translation: "Good afternoon",
    status: "done",
    edited: false,
    at: 1000,
    ...over,
  } as Turn;
}

/** The region that is supposed to be read out on the receiving side. */
function announced(side: Side): string {
  const node = document.getElementById(`interpreter-announce-${side}`);
  expect(node, "the receiving card has a live region").not.toBeNull();
  expect(node!.getAttribute("aria-live")).toBe("polite");
  return node!.textContent ?? "";
}

describe("the translation on the receiving card", () => {
  it("stands in the content of a live region, not only in a value", () => {
    render(<ConversationView {...BASE} turns={[turn()]} />);

    // The left side spoke, so the right card carries the translation.
    expect(announced("right")).toBe("Good afternoon");
    // And the speaker's own card announces nothing of it.
    expect(announced("left")).toBe("");
  });

  it("changes its content when a corrected sentence is translated again", () => {
    const view = render(<ConversationView {...BASE} turns={[turn()]} />);
    expect(announced("right")).toBe("Good afternoon");

    view.rerender(
      <ConversationView {...BASE} turns={[turn({ translation: "Good day to you" })]} />,
    );

    expect(announced("right")).toBe("Good day to you");
  });

  it("stays quiet while the translation is still running", () => {
    render(<ConversationView {...BASE} turns={[turn({ status: "translating", translation: "" })]} />);

    expect(announced("right")).toBe("");
  });

  it("is still in the read only field, so it can be read and copied", () => {
    render(<ConversationView {...BASE} turns={[turn()]} />);

    const field = document.getElementById("interpreter-field-right") as HTMLTextAreaElement;
    expect(field.value).toBe("Good afternoon");
    expect(field.readOnly).toBe(true);
    // The attribute that never worked here is gone.
    expect(field.getAttribute("aria-live")).toBeNull();
  });
});

describe("the status line", () => {
  it("is a region that announces itself", () => {
    render(<ConversationView {...BASE} />);

    const lines = screen.getAllByRole("status");
    expect(lines.length).toBe(2);
  });

  it("carries the microphone error where it can be heard", () => {
    render(<ConversationView {...BASE} notice={{ side: "left", kind: "mic" }} />);

    const texts = screen.getAllByRole("status").map((n) => n.textContent);
    expect(texts).toContain("Das Mikrofon ist nicht freigegeben.");
  });
});

describe("the Speak button", () => {
  it("is off and says why when no speech model is configured", () => {
    render(<ConversationView {...BASE} stt={false} />);

    for (const button of screen.getAllByRole("button", { name: /Sprechen|Speak/ })) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
    const texts = screen.getAllByRole("status").map((n) => n.textContent);
    expect(texts).toContain("No speech recognition is configured. Typing still works.");
  });

  it("is off and names http when the origin is not a secure one", () => {
    render(<ConversationView {...BASE} secureContext={false} />);

    for (const button of screen.getAllByRole("button", { name: /Sprechen|Speak/ })) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
    const texts = screen.getAllByRole("status").map((n) => n.textContent);
    expect(texts).toContain("The microphone needs https or localhost. Typing still works.");
    expect(texts).not.toContain("The microphone is not allowed.");
  });

  it("is live when a model is there and the origin is secure", () => {
    render(<ConversationView {...BASE} />);

    for (const button of screen.getAllByRole("button", { name: /Sprechen|Speak/ })) {
      expect((button as HTMLButtonElement).disabled).toBe(false);
    }
  });
});

describe("the history", () => {
  it("marks each line with the language it is written in", () => {
    render(<ConversationView {...BASE} turns={[turn()]} />);

    const entry = document.querySelector("ol li")!;
    const original = entry.querySelector("p.font-semibold")!;
    const translation = original.nextElementSibling!.querySelector("p")!;
    expect(original.getAttribute("lang")).toBe("de");
    expect(translation.getAttribute("lang")).toBe("en");
    expect(original.textContent).toBe("Guten Tag");
    expect(translation.textContent).toBe("Good afternoon");
  });
});
