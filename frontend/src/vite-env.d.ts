/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" in the static GitHub Pages build (frontend/.env.static). */
  readonly VITE_STATIC?: string;
}
