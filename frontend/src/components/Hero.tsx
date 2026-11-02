import { useState } from "react";

const GITHUB_URL = "https://github.com/namyaa6/CollectionsLab";
const LINKEDIN_URL = "https://www.linkedin.com/in/namyajain6";
const INTRO_KEY = "collectionslab.showIntro";

/**
 * Show/hide the intro, remembered in this browser. localStorage can be missing or throw
 * (private windows, blocked storage), so every access is wrapped and the intro shows by default.
 */
export function useIntroPreference(): [boolean, () => void] {
  const [show, setShow] = useState(() => {
    try {
      return localStorage.getItem(INTRO_KEY) !== "hidden";
    } catch {
      return true;
    }
  });
  function toggle() {
    setShow((cur) => {
      try {
        localStorage.setItem(INTRO_KEY, cur ? "hidden" : "shown");
      } catch {
        // storage unavailable: the choice lasts until the page is reloaded
      }
      return !cur;
    });
  }
  return [show, toggle];
}

export default function Hero({ showIntro, onToggle }: { showIntro: boolean; onToggle: () => void }) {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-head">
        <div>
          <h1 id="hero-title" className="hero-title">CollectionsLab</h1>
          <p className="hero-sub">Measuring how prompt changes affect an AI collections voice agent</p>
        </div>
        <div className="hero-side">
          <p className="byline">
            Built by Namya Jain · <a href={GITHUB_URL}>GitHub</a> · <a href={LINKEDIN_URL}>LinkedIn</a>
          </p>
          <button className="btn ghost sm" onClick={onToggle} aria-expanded={showIntro}
            aria-controls="landing-intro">
            {showIntro ? "Hide intro" : "Show intro"}
          </button>
        </div>
      </div>
      {showIntro && (
        <p className="hero-intro" id="landing-intro">
          An AI agent phones business customers about unpaid invoices. Four versions of its
          instructions (its "prompt") were each tested on the same 14 simulated calls with
          difficult customers, and every call was graded twice: by code checks and by an AI judge.
        </p>
      )}
    </section>
  );
}
