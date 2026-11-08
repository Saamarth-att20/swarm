"use client";

import { Radio } from "lucide-react";
import { cn } from "@/lib/cn";
import type { Capabilities } from "@/lib/types";

export type CallMode = "simulated" | "live";

export function ModePicker({ mode, onChange, caps }: { mode: CallMode; onChange: (m: CallMode) => void; caps: Capabilities | null }) {
  const liveReady = caps?.live_available ?? false;
  return (
    <div>
      <fieldset className="text-sm">
        <legend className="mb-1.5 font-medium">Calls</legend>
        <div className="flex h-11 rounded-md border border-line bg-card p-1" role="radiogroup">
          {(["simulated", "live"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              disabled={m === "live" && !liveReady}
              onClick={() => onChange(m)}
              className={cn("flex-1 whitespace-nowrap rounded px-2 text-sm font-medium transition-colors", mode === m ? "bg-ink text-paper" : "text-ink-soft hover:text-ink", m === "live" && !liveReady && "cursor-not-allowed opacity-50")}
            >
              {m === "simulated" ? "Practice run" : "Real phones"}
            </button>
          ))}
        </div>
      </fieldset>
      {caps && !liveReady && (
        <p className="mt-3 flex items-start gap-2 text-[13px] text-ink-soft">
          <Radio className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>Practice runs use made-up organizations and need no keys. Real phone calls need: {caps.live_missing.join("; ")}.</span>
        </p>
      )}
      {caps && liveReady && mode === "live" && (
        <p className="mt-3 text-[13px] text-ink-soft">Every call opens by telling the person they're speaking with an AI assistant. {caps.places_provider === "google" && caps.demo_targets === 0 ? "Real businesses near your location are phoned in parallel." : caps.demo_targets > 0 ? `Test mode: calls go only to your ${caps.demo_targets} demo numbers.` : ""}</p>
      )}
    </div>
  );
}
