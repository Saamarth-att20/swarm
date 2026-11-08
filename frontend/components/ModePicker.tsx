"use client";

import type { Capabilities } from "@/lib/types";

export type CallMode = "simulated" | "live";

/** Practice run or real phones, with a one-line note on what each does. */
export function ModePicker({ mode, onChange, caps }: { mode: CallMode; onChange: (m: CallMode) => void; caps: Capabilities | null }) {
  const liveReady = caps?.live_available ?? false;

  let note = "See how Swarm Dial works with made-up businesses. No calls are placed.";
  if (mode === "live" && liveReady) {
    const where =
      caps?.places_provider === "google" && caps.demo_targets === 0
        ? "Real businesses near your location are phoned in parallel."
        : caps && caps.demo_targets > 0
          ? `Test mode: calls go only to your ${caps.demo_targets} demo numbers.`
          : "";
    note = `Every call opens by telling the person they’re speaking with an AI assistant. ${where}`.trim();
  }

  return (
    <div className="mode-wrap">
      <div className="segmented" role="radiogroup" aria-label="Calls">
        {(["simulated", "live"] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={mode === m}
            className={mode === m ? "active" : ""}
            disabled={m === "live" && !liveReady}
            onClick={() => onChange(m)}
          >
            {m === "simulated" ? "Practice run" : "Real phones"}
          </button>
        ))}
      </div>
      <div className="mode-note">
        <p>{note}</p>
        {caps && !liveReady && (
          <details>
            <summary>Real phones aren’t set up yet. What’s missing?</summary>
            <p>{caps.live_missing.join("; ")}.</p>
          </details>
        )}
      </div>
    </div>
  );
}