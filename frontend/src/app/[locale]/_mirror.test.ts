import { afterEach, describe, expect, it, vi } from "vitest";
import { createMirror } from "./_mirror";
import type { Turn } from "./_types";

const turn = (id: string, original: string): Turn => ({
  id, side: "left", source: "typed", original, translation: "", status: "done", at: 1, edited: false,
});

function setup() {
  const sent: string[] = [];
  const resolvers: (() => void)[] = [];
  const put = (t: Turn) => {
    sent.push(`${t.id}:${t.original}`);
    return new Promise<void>((resolve) => resolvers.push(resolve));
  };
  return { sent, resolvers, mirror: createMirror(put, 1000) };
}

afterEach(() => vi.useRealTimers());

describe("mirror to the server", () => {
  it("sends the first version at once and then only the newest, one a second", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gu"));
    mirror.push(turn("a", "Gut"));
    expect(sent).toEqual(["a:G"]);

    resolvers[0]();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toEqual(["a:G"]);
    await vi.advanceTimersByTimeAsync(1000);
    expect(sent).toEqual(["a:G", "a:Gut"]);
  });

  it("keeps two sentences apart", () => {
    const { sent, mirror } = setup();
    mirror.push(turn("a", "Hallo"));
    mirror.push(turn("b", "Hello"));
    expect(sent).toEqual(["a:Hallo", "b:Hello"]);
  });

  it("flush sends everything still waiting and waits for the answer", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gut"));
    let done = false;
    const flushing = mirror.flush().then(() => { done = true; });
    resolvers[0]();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toEqual(["a:G", "a:Gut"]);
    expect(done).toBe(false);
    resolvers[1]();
    await flushing;
    expect(done).toBe(true);
  });

  it("cancel drops what is still waiting", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gut"));
    mirror.cancel();
    resolvers[0]();
    await vi.advanceTimersByTimeAsync(2000);
    expect(sent).toEqual(["a:G"]);
  });
});
