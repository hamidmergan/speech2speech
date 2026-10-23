import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { backendApi as BackendApi, onAccessLocked as OnAccessLocked } from "./api";

// The listener set lives in the module, so every test needs its own module copy.
let backendApi: typeof BackendApi;
let onAccessLocked: typeof OnAccessLocked;

beforeEach(async () => {
  vi.resetModules();
  const mod = await import("./api");
  backendApi = mod.backendApi;
  onAccessLocked = mod.onAccessLocked;
});

function answerWith(status: number, body: unknown) {
  const spy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the request itself", () => {
  it("goes to the backend prefix and carries the cookies", async () => {
    const spy = answerWith(200, { sessions: [] });

    await backendApi.fetch("/interpreter/sessions");

    expect(spy).toHaveBeenCalledTimes(1);
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/interpreter/sessions");
    expect(init.credentials).toBe("include");
  });

  it("asks for the language the page is shown in", async () => {
    const spy = answerWith(200, {});

    await backendApi.fetch("/interpreter/sessions");

    expect(new Headers(spy.mock.calls[0][1].headers).get("Accept-Language")).toBe("de");
  });

  it("leaves a language the caller set alone", async () => {
    const spy = answerWith(200, {});

    await backendApi.fetch("/interpreter/sessions", { headers: { "Accept-Language": "en" } });

    expect(new Headers(spy.mock.calls[0][1].headers).get("Accept-Language")).toBe("en");
  });
});

describe("a 401 from the access password", () => {
  it("tells the page to ask for the password again", async () => {
    answerWith(401, { detail: "Enter the access password." });
    let locked = 0;
    onAccessLocked(() => { locked += 1; });

    await backendApi.fetch("/interpreter/sessions");

    expect(locked).toBe(1);
  });

  it("leaves the answer readable all the same", async () => {
    answerWith(401, { detail: "Enter the access password." });

    const r = await backendApi.fetch("/interpreter/sessions");

    expect(r.status).toBe(401);
    expect(await r.json()).toEqual({ detail: "Enter the access password." });
  });

  it("stops telling the page once the listener is gone", async () => {
    answerWith(401, { detail: "nope" });
    let locked = 0;
    const off = onAccessLocked(() => { locked += 1; });
    off();

    await backendApi.fetch("/interpreter/sessions");

    expect(locked).toBe(0);
  });
});

describe("error bodies", () => {
  it("raise the detail the backend sent", async () => {
    answerWith(409, { detail: "This conversation is full. Start a new one." });

    await expect(backendApi.postJson("/interpreter/sessions/s1/turns/t1", {}))
      .rejects.toThrow("This conversation is full. Start a new one.");
  });

  it("raise a readable sentence instead of a status code", async () => {
    answerWith(422, { detail: [{ loc: ["body", "at"], msg: "field required" }] });

    await expect(backendApi.postJson("/interpreter/sessions", {}))
      .rejects.toThrow("Da ist etwas schiefgelaufen. Bitte versuche es erneut.");
  });

  it("do not stumble over a body without JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 500 })));

    await expect(backendApi.getJson("/interpreter/sessions")).rejects.toThrow();
  });
});
