import { describe, expect, it } from "vitest";
import type { QueueItem, VoiceLike } from "./tts";
import { createPlayer, DEBTOR_PITCH_SHIFT, type PlayerSettings, type PlayState } from "./ttsPlayer";

class FakeUtterance {
  voice: VoiceLike | null = null;
  lang = "";
  pitch = 1;
  rate = 1;
  onend: (() => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  constructor(public text: string) {}
}

const AGENT: VoiceLike = { name: "A", lang: "en-IN", voiceURI: "a", localService: true };
const DEBTOR: VoiceLike = { name: "D", lang: "en-GB", voiceURI: "d", localService: true };

const QUEUE: QueueItem[] = [
  { turn: 0, speaker: "agent", text: "one" },
  { turn: 2, speaker: "debtor", text: "two" },
  { turn: 3, speaker: "agent", text: "three" },
];

function setup(queue = QUEUE) {
  const spoken: FakeUtterance[] = [];
  const calls: string[] = [];
  const turns: (number | null)[] = [];
  const states: PlayState[] = [];
  const errors: string[] = [];
  const settings: PlayerSettings<VoiceLike> = { agent: AGENT, debtor: DEBTOR, samePitchShift: false, rate: 1 };
  const synth = {
    speak: (u: FakeUtterance) => { calls.push("speak"); spoken.push(u); },
    cancel: () => calls.push("cancel"),
    pause: () => calls.push("pause"),
    resume: () => calls.push("resume"),
  };
  const player = createPlayer({
    synth, makeUtterance: (t) => new FakeUtterance(t), queue, getSettings: () => settings,
    onTurn: (t) => turns.push(t),
    onState: (s, e) => { states.push(s); if (e) errors.push(e); },
  });
  const last = () => spoken[spoken.length - 1];
  return { player, spoken, calls, turns, states, errors, settings, last };
}

describe("createPlayer", () => {
  it("speaks the queue in order, reports each turn, then null and idle", () => {
    const t = setup();
    t.player.play();
    t.last().onend!();
    t.last().onend!();
    t.last().onend!();
    expect(t.spoken.map((u) => u.text)).toEqual(["one", "two", "three"]);
    expect(t.turns).toEqual([0, 2, 3, null]);
    expect(t.states).toEqual(["playing", "idle"]);
  });

  it("gives each speaker their voice and shifts debtor pitch only when asked", () => {
    const t = setup();
    t.player.play();
    expect([t.last().voice, t.last().lang, t.last().pitch]).toEqual([AGENT, "en-IN", 1]);
    t.last().onend!();
    expect([t.last().voice, t.last().pitch]).toEqual([DEBTOR, 1]);
    t.settings.samePitchShift = true;
    t.settings.debtor = AGENT;
    t.player.play();
    t.last().onend!();
    expect([t.last().voice, t.last().pitch]).toEqual([AGENT, DEBTOR_PITCH_SHIFT]);
  });

  it("applies a speed change from the next turn", () => {
    const t = setup();
    t.player.play();
    t.settings.rate = 1.5;
    expect(t.last().rate).toBe(1);
    t.last().onend!();
    expect(t.last().rate).toBe(1.5);
  });

  it("ignores a late onend after stop (Chrome fires it after cancel)", () => {
    const t = setup();
    t.player.play();
    const first = t.last();
    t.player.stop();
    first.onend!();
    expect(t.spoken).toHaveLength(1);
    expect(t.turns).toEqual([0, null]);
    expect(t.states).toEqual(["playing", "idle"]);
  });

  it("ignores callbacks from a previous play after restarting", () => {
    const t = setup();
    t.player.play();
    const old = t.last();
    t.player.play();
    old.onend!();
    expect(t.spoken.map((u) => u.text)).toEqual(["one", "one"]);
  });

  it("ignores interrupted/canceled errors but stops on any other error", () => {
    const t = setup();
    t.player.play();
    t.last().onerror!({ error: "interrupted" });
    t.last().onerror!({ error: "canceled" });
    expect(t.states).toEqual(["playing"]);
    const failing = t.last();
    failing.onerror!({ error: "synthesis-failed" });
    failing.onend!(); // a following onend must not advance either
    expect(t.states).toEqual(["playing", "error"]);
    expect(t.errors).toEqual(["synthesis-failed"]);
    expect(t.turns).toEqual([0, null]);
    expect(t.spoken).toHaveLength(1);
  });

  it("delegates pause and resume to the synth", () => {
    const t = setup();
    t.player.play();
    t.player.pause();
    t.player.resume();
    expect(t.calls).toEqual(["cancel", "resume", "speak", "pause", "resume"]);
    expect(t.states).toEqual(["playing", "paused", "playing"]);
  });

  it("goes straight to idle for an empty queue", () => {
    const t = setup([]);
    t.player.play();
    expect(t.spoken).toHaveLength(0);
    expect(t.states).toEqual(["playing", "idle"]);
  });
});
