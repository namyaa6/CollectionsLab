// After `vite build --mode static`: copy the README hero screenshot to dist/og.png, the
// link-preview image named in index.html. Plain JS so the typechecked config needs no Node types.
import { copyFileSync } from "node:fs";

const from = new URL("../../docs/screenshots/hero.png", import.meta.url);
const to = new URL("../dist/og.png", import.meta.url);
copyFileSync(from, to);
console.log("copied hero.png -> dist/og.png");
