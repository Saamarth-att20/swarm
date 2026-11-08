"use client";

import { Star } from "lucide-react";
import { ListenButton } from "@/components/ListenButton";
import { StatusDot } from "@/components/design/StatusDot";
import { Wave } from "@/components/design/Wave";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { dotFor, isActiveState, snippetFor, statusLabel } from "@/lib/callDisplay";
import { cn } from "@/lib/cn";
import { miles } from "@/lib/format";
import { counts } from "@/lib/reducer";
import type { SwarmView } from "@/lib/types";

interface Props {
  swarm: SwarmView;
  expandedCallId: string | null;
  onToggle: (callId: string) => void;
}

/** One roomy card per business. Select a card to read the whole conversation; "Listen live" plays the call in your browser. */
export function AgentGrid({ swarm, expandedCallId, onToggle }: Props) {
  const k = counts(swarm);
  const kind = swarm.intent?.kind;
  const bestCallId = swarm.ranked?.bestCallId;

  return (
    <section className="agents-section" aria-label="Callers">
      <div className="section-row">
        <h2>Callers</h2>
        <span>
          {k.active} on the line · {k.done + k.failed} finished
        </span>
      </div>
      <ul className="caller-grid">
        {swarm.targetOrder.map((tid) => {
          const target = swarm.targets[tid];
          const call = swarm.calls[swarm.inquiryByTarget[tid]];
          if (!target) return null;
          const dot = dotFor(call, kind);
          const line = snippetFor(call, kind);
          const expanded = Boolean(call) && call.callId === expandedCallId;
          const best = Boolean(call) && call.callId === bestCallId;
          const active = isActiveState(call?.state);
          const tag =
            target.open_now === false ? "closed now" : target.tier === "backup" && target.source === "referral" ? "referred" : target.tier === "backup" ? "backup" : "";
          return (
            <li key={tid}>
              <article id={call ? `call-${call.callId}` : undefined} className={cn("caller-card", dot === "talking" && "talking", dot === "found" && "found", best && "best", expanded && "open")}>
                <button type="button" className="caller-main" disabled={!call} aria-expanded={call ? expanded : undefined} onClick={() => call && onToggle(call.callId)}>
                  <span className="caller-head">
                    <StatusDot status={dot} />
                    <span className="caller-name">
                      <strong>
                        {target.name}
                        {best && <Star className="h-3.5 w-3.5 shrink-0 fill-best text-[#B8901A]" aria-label="Best match" />}
                      </strong>
                      <small>
                        {miles(target.distance_miles)}
                        {tag ? ` · ${tag}` : ""}
                      </small>
                    </span>
                    {call?.state === "talking" && <Wave />}
                  </span>
                  {!expanded && <span className={cn("caller-line", line.tone)}>{line.text}</span>}
                </button>
                {expanded && call && <TranscriptPanel swarm={swarm} call={call} />}
                <div className="caller-foot">
                  <span>{statusLabel(call)}</span>
                  {swarm.mode === "live" && call && active ? (
                    <ListenButton callId={call.callId} active={active} />
                  ) : call ? (
                    <span className="hint">{expanded ? "Hide conversation" : "Read conversation"}</span>
                  ) : null}
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}