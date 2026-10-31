import { describe, expect, it } from "vitest";
import type { Turn } from "./callTypes";
import { buildQueue, englishVoices, pickVoices, resolveChoice, resolveVoice, type VoiceLike } from "./tts";

function turn(speaker: Turn["speaker"], text: string): Turn {
  return { speaker, text, tool_calls: [], latency_ms: 0, input_tokens: 0, output_tokens: 0,
    cached: false, error: null, self_check: null };
}

function voice(name: string, lang: string, localService = true): VoiceLike {
  return { name, lang, voiceURI: `uri:${name}`, localService };
}

describe("buildQueue", () => {
  it("skips turns with no speech and keeps the original turn indices", () => {
    const q = buildQueue([turn("agent", "Hello"), turn("agent", ""), turn("debtor", "  \n "), turn("debtor", "Hi")]);
    expect(q).toEqual([
      { turn: 0, speaker: "agent", text: "Hello" },
      { turn: 3, speaker: "debtor", text: "Hi" },
    ]);
  });

  it("passes the text through byte-identical (symbols, digits, whitespace)", () => {
    const text = "  Your balance is ₹1,70,300 on INV-2026-1022, due 02/11.\n\nPay by UPI.  ";
    expect(buildQueue([turn("agent", text)])[0].text).toBe(text);
  });
});

describe("pickVoices", () => {
  it("uses two different en-IN voices when there are two", () => {
    const c = pickVoices([voice("US", "en-US"), voice("Heera", "en-IN"), voice("Ravi", "en-IN")]);
    expect([c.agent?.lang, c.debtor?.lang]).toEqual(["en-IN", "en-IN"]);
    expect(c.agent?.voiceURI).not.toBe(c.debtor?.voiceURI);
    expect(c.samePitchShift).toBe(false);
  });

  it("falls back to another English voice for the debtor when only one en-IN exists", () => {
    const c = pickVoices([voice("US", "en-US"), voice("Heera", "en-IN"), voice("Hindi", "hi-IN")]);
    expect(c.agent?.name).toBe("Heera");
    expect(c.debtor?.name).toBe("US");
  });

  it("accepts the en_IN underscore form (Android)", () => {
    expect(pickVoices([voice("GB", "en-GB"), voice("Android", "en_IN")]).agent?.name).toBe("Android");
  });

  it("shares a single English voice and shifts the debtor's pitch", () => {
    const c = pickVoices([voice("Only", "en-US"), voice("French", "fr-FR")]);
    expect(c.agent?.name).toBe("Only");
    expect(c.debtor?.name).toBe("Only");
    expect(c.samePitchShift).toBe(true);
  });

  it("returns nulls when there is no English voice (browser default is used)", () => {
    expect(pickVoices([voice("Hindi", "hi-IN")])).toEqual({ agent: null, debtor: null, samePitchShift: false });
    expect(pickVoices([])).toEqual({ agent: null, debtor: null, samePitchShift: false });
  });

  it("prefers local voices over network ones within a tier", () => {
    const c = pickVoices([voice("Online", "en-IN", false), voice("Local", "en-IN", true)]);
    expect(c.agent?.name).toBe("Local");
    expect(c.debtor?.name).toBe("Online");
  });
});

describe("englishVoices", () => {
  it("lists every English voice, network ones included, en-IN first then by name", () => {
    const list = englishVoices([
      voice("Zed", "en-US"), voice("Hindi", "hi-IN"), voice("Neerja Online (Natural)", "en-IN", false),
      voice("Amy", "en-GB"), voice("Ravi", "en-IN"),
    ]);
    expect(list.map((v) => v.name)).toEqual(["Neerja Online (Natural)", "Ravi", "Amy", "Zed"]);
  });
});

describe("resolveVoice / resolveChoice", () => {
  const voices = [voice("Ravi", "en-IN"), voice("Heera", "en-IN"), voice("Neerja", "en-IN", false), voice("Hindi", "hi-IN")];

  it("uses a saved voice that is still available, else the fallback", () => {
    expect(resolveVoice(voices, "uri:Neerja", voices[0])?.name).toBe("Neerja");
    expect(resolveVoice(voices, "uri:Gone", voices[0])?.name).toBe("Ravi");
    expect(resolveVoice(voices, null, null)).toBeNull();
  });

  it("applies manual network-voice overrides and ignores saved non-English voices", () => {
    const c = resolveChoice(voices, "uri:Neerja", "uri:Hindi");
    expect(c.agent?.name).toBe("Neerja");
    expect(c.debtor?.name).toBe(pickVoices(voices).debtor?.name);
  });

  it("shifts pitch only when both speakers resolve to the same voice", () => {
    expect(resolveChoice(voices, "uri:Ravi", "uri:Ravi").samePitchShift).toBe(true);
    expect(resolveChoice(voices, null, null).samePitchShift).toBe(false);
  });
});
