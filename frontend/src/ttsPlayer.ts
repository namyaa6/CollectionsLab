// Plays a turn queue through speechSynthesis, one utterance per turn. The browser API is passed
// in (synth + makeUtterance), so tests drive it with fakes and no browser.
import type { QueueItem, VoiceChoice, VoiceLike } from "./tts";

export type PlayState = "idle" | "playing" | "paused" | "error";

/** The parts of SpeechSynthesisUtterance we set. Handler params are `any` so the real DOM type fits. */
export interface UtteranceLike<V> {
  voice: V | null;
  lang: string;
  pitch: number;
  rate: number;
  onend: ((ev: any) => void) | null;
  onerror: ((ev: any) => void) | null;
}

export interface SynthLike<U> {
  speak(u: U): void;
  cancel(): void;
  pause(): void;
  resume(): void;
}

export interface PlayerSettings<V extends VoiceLike> extends VoiceChoice<V> {
  rate: number;
}

interface Options<V extends VoiceLike, U extends UtteranceLike<V>> {
  synth: SynthLike<U>;
  makeUtterance: (text: string) => U;
  queue: QueueItem[];
  /** Read when each turn starts, so speed and voice changes apply from the next turn. */
  getSettings: () => PlayerSettings<V>;
  onTurn: (turn: number | null) => void;
  onState: (state: PlayState, error?: string) => void;
}

export const DEBTOR_PITCH_SHIFT = 1.15;

export function createPlayer<V extends VoiceLike, U extends UtteranceLike<V>>(opts: Options<V, U>) {
  const { synth, makeUtterance, queue, getSettings, onTurn, onState } = opts;
  // Bumped by play() and stop(). Chrome can fire onend / onerror("interrupted") after cancel(),
  // so callbacks from an older generation are ignored rather than advancing a stopped queue.
  let generation = 0;
  // Holding the utterance stops Chrome from garbage-collecting it mid-speech (onend never fires).
  let current: U | null = null;

  function speakAt(pos: number, gen: number) {
    if (gen !== generation) return;
    const item = queue[pos];
    if (!item) {
      current = null;
      onTurn(null);
      onState("idle");
      return;
    }
    const s = getSettings();
    const isAgent = item.speaker === "agent";
    const voice = isAgent ? s.agent : s.debtor;
    const u = makeUtterance(item.text);
    u.voice = voice;
    if (voice) u.lang = voice.lang;
    u.pitch = !isAgent && s.samePitchShift ? DEBTOR_PITCH_SHIFT : 1;
    u.rate = s.rate;
    u.onend = () => speakAt(pos + 1, gen);
    u.onerror = (e: { error: string }) => {
      if (gen !== generation || e.error === "interrupted" || e.error === "canceled") return;
      generation++;
      current = null;
      synth.cancel();
      onTurn(null);
      onState("error", e.error);
    };
    current = u;
    onTurn(item.turn);
    synth.speak(u);
  }

  return {
    play() {
      const gen = ++generation;
      synth.cancel();
      synth.resume(); // a synth cancelled while paused can stay paused in Chrome
      onState("playing");
      speakAt(0, gen);
    },
    pause() {
      synth.pause();
      onState("paused");
    },
    resume() {
      synth.resume();
      onState("playing");
    },
    stop() {
      generation++;
      current = null;
      synth.cancel();
      onTurn(null);
      onState("idle");
    },
    /** For tests: the utterance being spoken. */
    current: () => current,
  };
}
