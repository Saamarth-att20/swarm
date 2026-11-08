"use client";

import { useEffect, useRef } from "react";
import { Bot, Building2, Mic, PhoneOff } from "lucide-react";
import { cn } from "@/lib/cn";
import { ListenButton } from "@/components/ListenButton";
import { STATE_META, resultLine } from "@/lib/format";
import type { CallView, SwarmView } from "@/lib/types";

export function TranscriptPanel({ swarm, call }: { swarm: SwarmView; call: CallView | null }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true); // follow the conversation only while the reader is at the bottom of it
  const lines = call?.transcript ?? [];
  const tail = lines[lines.length - 1];
  useEffect(() => {
    stickRef.current = true; // a different call: start at its latest line
  }, [call?.callId]);
  useEffect(() => {
    // Scroll only this box. scrollIntoView() also scrolls the whole page, which yanked the dashboard back up
    // every time any call said something.
    const box = boxRef.current;
    if (box && stickRef.current) box.scrollTop = box.scrollHeight;
  }, [call?.callId, lines.length, tail?.text]);

  const target = call ? swarm.targets[call.targetId] : null;
  const meta = call ? STATE_META[call.state] : null;

  return (
    <section className="flex h-full min-h-[360px] flex-col rounded-panel border border-line bg-card" aria-label="Live transcript">
      <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg font-semibold">{target ? target.name : "Live transcript"}</h2>
          <p className="text-xs text-ink-soft">{target ? [target.address, target.phone].filter(Boolean).join(" · ") : "Pick a business to listen in."}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {meta && (
            <span className={cn("flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", `bg-${meta.color}/10 text-${meta.color}`)}>
              <span aria-hidden>{meta.emoji}</span>
              {meta.label}
            </span>
          )}
          {call && swarm.mode === "live" && (
            <ListenButton callId={call.callId} active={call.state === "talking" || call.state === "dialing" || call.state === "extracting"} />
          )}
        </div>
      </header>

      <div
        ref={boxRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
        className="scroll-quiet flex-1 space-y-3 overflow-y-auto px-4 py-4"
        aria-live="polite"
      >
        {!call && <Empty text="Calls appear here as soon as the first agent connects." />}
        {call && lines.length === 0 && <Empty text={call.state === "failed" ? call.reason ?? "This call didn't connect." : "Ringing. The transcript starts when someone picks up."} />}
        {lines.map((u) => {
          const agent = u.speaker === "agent";
          return (
            <div key={u.id} className={cn("flex gap-2.5", agent ? "" : "flex-row-reverse")}>
              <span className={cn("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full", agent ? "bg-ink text-paper" : "bg-line text-ink")}>
                {agent ? <Bot className="h-3.5 w-3.5" aria-label="Swarm agent" /> : <Building2 className="h-3.5 w-3.5" aria-label="Business" />}
              </span>
              <p className={cn("max-w-[85%] rounded-lg px-3 py-2 text-[14px] leading-relaxed", agent ? "bg-ink/[0.06]" : "border border-line bg-paper", !u.final && "text-ink-soft")}>
                {u.text}
                {!u.final && <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 bg-ink-soft animate-caret" aria-hidden />}
              </p>
            </div>
          );
        })}
      </div>

      {call?.state === "failed" && lines.length > 0 && (
        <footer className="flex items-center gap-2 border-t border-line bg-failed/[0.06] px-4 py-2.5 text-sm">
          <PhoneOff className="h-4 w-4 text-failed" aria-hidden />
          <span className="font-medium">Ended:</span>
          <span className="text-ink-soft">{call.reason ?? "The call failed"}</span>
        </footer>
      )}

      {call?.result && (
        <footer className="flex items-center gap-2 border-t border-line bg-extracting/[0.06] px-4 py-2.5 text-sm">
          <Mic className="h-4 w-4 text-extracting" aria-hidden />
          <span className="font-medium">Extracted:</span>
          <span className="text-ink-soft">{resultLine(call.result, swarm.intent?.kind ?? "product")}</span>
        </footer>
      )}
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="py-10 text-center text-sm text-ink-faint">{text}</p>;
}