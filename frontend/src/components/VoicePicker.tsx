import type { VoiceLike } from "../tts";

export type Speaker = "agent" | "debtor";

const KEYS: Record<Speaker, string> = { agent: "tts.agentVoice", debtor: "tts.debtorVoice" };

// localStorage can throw (private mode, blocked site data); then we just use the defaults.
export function loadVoicePref(who: Speaker): string | null {
  try {
    return window.localStorage.getItem(KEYS[who]);
  } catch {
    return null;
  }
}

export function saveVoicePref(who: Speaker, voiceURI: string): void {
  try {
    window.localStorage.setItem(KEYS[who], voiceURI);
  } catch {
    // not remembered; the choice still applies for this page
  }
}

function voiceLabel(v: VoiceLike): string {
  return `${v.name} (${v.lang})${v.localService ? "" : " · online"}`;
}

interface Props {
  voices: VoiceLike[];
  agent: VoiceLike | null;
  debtor: VoiceLike | null;
  onChange: (who: Speaker, voiceURI: string) => void;
}

/** Manual voice override per speaker. Any English voice, including network ("online") ones. */
export default function VoicePicker({ voices, agent, debtor, onChange }: Props) {
  if (voices.length === 0) return null;
  const select = (who: Speaker, label: string, value: VoiceLike | null) => (
    <label className="voice-pick">
      {label}
      <select value={value?.voiceURI ?? ""} onChange={(e) => onChange(who, e.target.value)}>
        {voices.map((v) => <option key={v.voiceURI} value={v.voiceURI}>{voiceLabel(v)}</option>)}
      </select>
    </label>
  );
  return (
    <div className="voice-picker hint">
      {select("agent", "Agent voice", agent)}
      {select("debtor", "Debtor voice", debtor)}
    </div>
  );
}
