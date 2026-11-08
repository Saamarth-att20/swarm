import type { Config } from "tailwindcss";

const STATES = ["queued", "dialing", "talking", "extracting", "done", "failed"];

const config: Config = {
  // State colours are composed dynamically (lib/format.ts), so Tailwind can't see them in source.
  safelist: STATES.flatMap((c) => [`bg-${c}`, `text-${c}`, `bg-${c}/10`, `border-${c}`]),
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#EEF0EC",
        card: "#F8F9F6",
        ink: { DEFAULT: "#12203A", soft: "#4A566B", faint: "#8A93A3" },
        line: "#CDD3CC",
        // call-state palette: each state has a fixed meaning everywhere in the UI
        queued: "#8A93A3",
        dialing: "#D98E04",
        talking: "#2557E6",
        extracting: "#7C4DDB",
        done: "#17895F",
        failed: "#C93B3B",
        best: "#F2C94C",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"Public Sans Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: { panel: "10px" },
      keyframes: {
        caret: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0" } },
        dash: { to: { strokeDashoffset: "-24" } },
      },
      animation: { caret: "caret 1s steps(1) infinite", dash: "dash 1.2s linear infinite" },
    },
  },
  plugins: [],
};
export default config;
