"use client";

import { motion } from "framer-motion";
import { ChevronRight, Star } from "lucide-react";
import { cn } from "@/lib/cn";
import { STATE_META, miles, resultLine } from "@/lib/format";
import type { CallState, SwarmView } from "@/lib/types";

const STEPS: CallState[] = ["dialing", "talking", "extracting", "completed"];

function Steps({ state }: { state: CallState }) {
  const failed = state === "failed";
  const at = STATE_META[state].step;
  return (
    <div className="flex items-center gap-1" aria-hidden>
      {STEPS.map((s, i) => {
        const reached = at >= i + 1 && !(failed && i === 3);
        return <span key={s} className={cn("h-1 flex-1 rounded-full", reached ? `bg-${STATE_META[failed ? "failed" : state].color}` : "bg-line")} />;
      })}
    </div>
  );
}

export function AgentGrid({ swarm, selectedCallId, onSelect }: { swarm: SwarmView; selectedCallId: string | null; onSelect: (id: string) => void }) {
  const bestCall = swarm.ranked?.bestCallId;
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {swarm.targetOrder.map((tid) => {
        const target = swarm.targets[tid];
        const call = swarm.calls[swarm.inquiryByTarget[tid]];
        const state: CallState = call?.state ?? "queued";
        const meta = STATE_META[state];
        const selected = call?.callId === selectedCallId;
        const best = call && call.callId === bestCall;
        return (
          <motion.li layout key={tid} transition={{ duration: 0.2 }}>
            <button
              disabled={!call}
              onClick={() => call && onSelect(call.callId)}
              className={cn(
                "group w-full rounded-panel border bg-card p-3.5 text-left transition-colors disabled:cursor-default",
                selected ? "border-ink shadow-[0_0_0_1px_#12203A]" : "border-line hover:border-ink-faint",
                best && "border-best bg-[#FBF6E3]",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium leading-snug">{target.name}</span>
                    {best && <Star className="h-3.5 w-3.5 shrink-0 fill-best text-[#B8901A]" aria-label="Best match" />}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-soft">
                    {miles(target.distance_miles)}
                    {target.open_now === false ? " · closed now" : ""}
                    {target.tier === "backup" && target.source === "referral" ? " · referred" : target.tier === "backup" ? " · backup" : ""}
                  </div>
                </div>
                <span className={cn("flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", `bg-${meta.color}/10 text-${meta.color}`)}>
                  <span aria-hidden>{meta.emoji}</span>
                  {call ? meta.label : "Standing by"}
                </span>
              </div>
              <div className="mt-3">
                <Steps state={state} />
              </div>
              <div className="mt-2.5 flex min-h-[1.25rem] items-center justify-between gap-2 text-[13px]">
                <span className={cn("truncate", state === "failed" ? "text-failed" : "text-ink-soft")}>
                  {call?.result ? resultLine(call.result, swarm.intent?.kind ?? "product") : state === "failed" ? call?.reason ?? "Call failed" : call?.state === "talking" ? lastLine(call.transcript) : ""}
                </span>
                {call && <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" aria-hidden />}
              </div>
            </button>
          </motion.li>
        );
      })}
    </ul>
  );
}

function lastLine(t: { text: string; speaker: string }[]): string {
  const last = t[t.length - 1];
  return last ? `“${last.text}”` : "";
}
