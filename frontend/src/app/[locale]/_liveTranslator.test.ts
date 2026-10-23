import { afterEach, describe, expect, it, vi } from "vitest";
import { createLiveTranslator } from "./_liveTranslator";

function setup(gap = 1000) {
  const calls: string[] = [];
  const resolvers: ((value: string) => void)[] = [];
  const run = (text: string) => {
    calls.push(text);
    return new Promise<string>((resolve) => resolvers.push(resolve));
  };
  const results: [string, string][] = [];
  const live = createLiveTranslator(run, (text, translation) => results.push([text, translation]), gap);
  return { calls, resolvers, results, live };
}

afterEach(() => vi.useRealTimers());

describe("live translation", () => {
  it("sends one request at a time and then the newest text", async () => {
    vi.useFakeTimers();
    const { calls, resolvers, results, live } = setup();
    live.schedule("Guten");
    live.schedule("Guten Tag");
    live.schedule("Guten Tag, worum");
    expect(calls).toEqual(["Guten"]);

    resolvers[0]("Good");
    await vi.advanceTimersByTimeAsync(0);
    expect(results).toEqual([["Guten", "Good"]]);
    expect(calls).toEqual(["Guten"]);

    await vi.advanceTimersByTimeAsync(1000);
    expect(calls).toEqual(["Guten", "Guten Tag, worum"]);
  });

  it("drops every answer still on its way after a cancel", async () => {
    vi.useFakeTimers();
    const { resolvers, results, live } = setup();
    live.schedule("Hallo");
    live.cancel();
    resolvers[0]("Hello");
    await vi.advanceTimersByTimeAsync(0);
    expect(results).toEqual([]);
  });

  it("ignores empty text", () => {
    const { calls, live } = setup();
    live.schedule("   ");
    expect(calls).toEqual([]);
  });
});
