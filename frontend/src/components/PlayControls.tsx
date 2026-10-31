import { useEffect, useMemo, useRef, useState } from "react";
import type { Turn } from "../callTypes";
import { buildQueue, englishVoices, RATES, resolveChoice } from "../tts";
import { createPlayer, type PlayerSettings, type PlayState } from "../ttsPlayer";
import VoicePicker, { loadVoicePref, saveVoicePref, type Speaker } from "./VoicePicker";

interface Props {
  turns: Turn[];
  /** Index of the turn being spoken, or null when nothing is. */
  onSpeaking: (turn: number | null) => void;
}

const supported = typeof window !== "undefined" && "speechSynthesis" in window;

export default function PlayControls(props: Props) {
  if (!supported) {
    return (
      <div className="play-controls">
        <button className="btn sm" disabled title="This browser has no speechSynthesis">▶ Play</button>
        <span className="hint">Speech playback isn't supported in this browser</span>
      </div>
    );
  }
  return <Player {...props} />;
}

function Player({ turns, onSpeaking }: Props) {
  const synth = window.speechSynthesis;
  const queue = useMemo(() => buildQueue(turns), [turns]);

  // Chrome loads the voice list asynchronously: the first getVoices() is often empty, and a
  // "voiceschanged" event fires when it is ready. The cleanup function unsubscribes on unmount.
  const [voices, setVoices] = useState(() => synth.getVoices());
  useEffect(() => {
    const update = () => setVoices(synth.getVoices());
    synth.addEventListener("voiceschanged", update);
    return () => synth.removeEventListener("voiceschanged", update);
  }, [synth]);

  const [saved, setSaved] = useState(() => ({ agent: loadVoicePref("agent"), debtor: loadVoicePref("debtor") }));
  const [rate, setRate] = useState(1);
  const [state, setState] = useState<PlayState>("idle");
  const [error, setError] = useState<string | null>(null);
  const english = useMemo(() => englishVoices(voices), [voices]);
  const choice = useMemo(() => resolveChoice(voices, saved.agent, saved.debtor), [voices, saved]);

  // The player reads settings when each turn starts. A ref is a mutable box that survives
  // re-renders without causing them, so the running player always sees the latest choice.
  const settings = useRef<PlayerSettings<SpeechSynthesisVoice>>({ ...choice, rate });
  useEffect(() => {
    settings.current = { ...choice, rate };
  }, [choice, rate]);

  const player = useRef<ReturnType<typeof createPlayer<SpeechSynthesisVoice, SpeechSynthesisUtterance>> | null>(null);
  useEffect(() => () => player.current?.stop(), []); // leaving the page stops the audio

  function play() {
    player.current?.stop();
    setError(null);
    player.current = createPlayer({
      synth,
      makeUtterance: (text) => new SpeechSynthesisUtterance(text),
      queue,
      getSettings: () => settings.current,
      onTurn: onSpeaking,
      onState: (s, err) => {
        setState(s);
        if (err) setError(err);
      },
    });
    player.current.play();
  }

  function pickVoice(who: Speaker, voiceURI: string) {
    saveVoicePref(who, voiceURI);
    setSaved((prev) => ({ ...prev, [who]: voiceURI }));
  }

  const active = state === "playing" || state === "paused";
  return (
    <div className="play-controls">
      <div className="play-row">
        {!active && (
          <button className="btn primary sm" onClick={play} disabled={queue.length === 0}
            title={queue.length === 0 ? "No spoken turns" : "Read the call aloud"}>▶ Play</button>
        )}
        {state === "playing" && <button className="btn sm" onClick={() => player.current?.pause()}>❚❚ Pause</button>}
        {state === "paused" && <button className="btn sm" onClick={() => player.current?.resume()}>▶ Resume</button>}
        {active && <button className="btn sm" onClick={() => player.current?.stop()}>■ Stop</button>}
        <label className="hint speed">
          Speed
          <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
            {RATES.map((r) => <option key={r} value={r}>{r}x</option>)}
          </select>
        </label>
      </div>
      <VoicePicker voices={english} agent={choice.agent} debtor={choice.debtor} onChange={pickVoice} />
      {error && <span className="turn-error">Playback failed: {error}</span>}
    </div>
  );
}
