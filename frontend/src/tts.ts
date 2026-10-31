// Pure logic for transcript playback: which turns to speak and which voices to use.
// No DOM access here; the browser speechSynthesis API is driven by ttsPlayer.ts.
import type { Turn } from "./callTypes";

export interface QueueItem {
  /** Index into the full turns array, so the viewer can highlight it. */
  turn: number;
  speaker: "agent" | "debtor";
  text: string;
}

/** The fields of SpeechSynthesisVoice we use, so tests need no browser types. */
export interface VoiceLike {
  name: string;
  lang: string;
  voiceURI: string;
  localService: boolean;
}

export interface VoiceChoice<V extends VoiceLike = VoiceLike> {
  agent: V | null;
  debtor: V | null;
  /** Both speakers share one voice, so the debtor is spoken at a higher pitch. */
  samePitchShift: boolean;
}

export const RATES = [0.75, 1, 1.25, 1.5] as const;

/**
 * Turns with speech, in order. Text is passed through unchanged: hearing how a real TTS reads
 * v1's symbols and digits is the point of the demo.
 */
export function buildQueue(turns: Turn[]): QueueItem[] {
  const queue: QueueItem[] = [];
  turns.forEach((t, i) => {
    if (t.text.trim() !== "") queue.push({ turn: i, speaker: t.speaker, text: t.text });
  });
  return queue;
}

function normLang(lang: string): string {
  return lang.replace("_", "-").toLowerCase();
}

/** 0 = English (India), 1 = other English, null = not English. */
function tier(v: VoiceLike): number | null {
  const lang = normLang(v.lang);
  if (lang === "en-in") return 0;
  if (lang === "en" || lang.startsWith("en-")) return 1;
  return null;
}

/** Every English voice (local and network), en-IN first, then by name. For the dropdowns. */
export function englishVoices<V extends VoiceLike>(voices: V[]): V[] {
  return voices
    .filter((v) => tier(v) !== null)
    .sort((a, b) => tier(a)! - tier(b)! || a.name.localeCompare(b.name));
}

/**
 * Default voices: en-IN before other English, local before network within a tier (Chrome's
 * network voices tend to cut out on long utterances). The debtor gets a different voice when
 * one exists; otherwise both share one and the debtor's pitch is raised.
 */
export function pickVoices<V extends VoiceLike>(voices: V[]): VoiceChoice<V> {
  const ranked = englishVoices(voices).sort(
    (a, b) => tier(a)! - tier(b)! || Number(b.localService) - Number(a.localService),
  );
  const agent = ranked[0] ?? null;
  if (!agent) return { agent: null, debtor: null, samePitchShift: false };
  const debtor = ranked.find((v) => v.voiceURI !== agent.voiceURI) ?? agent;
  return { agent, debtor, samePitchShift: debtor === agent };
}

/** The saved voice if it is still available, else the fallback (a missing voice or another browser). */
export function resolveVoice<V extends VoiceLike>(voices: V[], savedURI: string | null, fallback: V | null): V | null {
  return voices.find((v) => v.voiceURI === savedURI) ?? fallback;
}

/** Final choice after manual overrides; pitch shift only when both resolve to the same voice. */
export function resolveChoice<V extends VoiceLike>(voices: V[], savedAgent: string | null,
                                                   savedDebtor: string | null): VoiceChoice<V> {
  const english = englishVoices(voices);
  const defaults = pickVoices(english);
  const agent = resolveVoice(english, savedAgent, defaults.agent);
  const debtor = resolveVoice(english, savedDebtor, defaults.debtor);
  return { agent, debtor, samePitchShift: agent != null && agent.voiceURI === debtor?.voiceURI };
}
