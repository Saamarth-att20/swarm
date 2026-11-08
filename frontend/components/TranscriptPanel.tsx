"use client";

import { useEffect, useRef } from "react";
import { Bot, Building2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { resultLine } from "@/lib/format";
import type { CallView, SwarmView } from "@/lib/types";

/** The full conversation for one call. It opens inside that call's card; the live-listen button stays on the card itself. */
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

  return (
    <div aria-label="Live transcript">
      <div
        ref={boxRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
        className="transcript-box"
        aria-live="polite"
      >
        {!call && <p className="transcript-empty">Calls appear here as soon as the first agent connects.</p>}
        {call && lines.length === 0 && (
          <p className="transcript-empty">{call.state === "failed" ? call.reason ?? "This call didn't connect." : "Ringing. The transcript starts when someone picks up."}</p>
        )}
        {lines.map((u) => {
          const agent = u.speaker === "agent";
          return (
            <div key={u.id} className={cn("bubble-row", agent ? "agent" : "biz")}>
              <span className="bubble-avatar">
                {agent ? <Bot className="h-3.5 w-3.5" aria-label="Swarm agent" /> : <Building2 className="h-3.5 w-3.5" aria-label="Business" />}
              </span>
              <p className={cn("bubble", !u.final && "partial")}>
                {u.text}
                {!u.final && <span className="caret" aria-hidden />}
              </p>
            </div>
          );
        })}
      </div>
      {call?.state === "failed" && lines.length > 0 && (
        <p className="transcript-note bad">
          <strong>Ended:</strong> {call.reason ?? "The call failed"}
        </p>
      )}
      {call?.result && (
        <p className="transcript-note good">
          <strong>Noted:</strong> {resultLine(call.result, swarm.intent?.kind ?? "product")}
        </p>
      )}
    </div>
  );
}