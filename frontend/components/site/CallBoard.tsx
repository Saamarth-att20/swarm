"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  BOARD_EVENTS, BOARD_QUERY, BOARD_ROWS, LOOP_MS, WINNER_AT, WINNER_LINE, WINNER_ROW, boardAt, type BoardState,
} from "@/lib/boardScript";

/** Brighter versions of the dashboard's call-state colours, tuned to read on the dark board. Same meanings. */
const DOT: Record<BoardState, string> = {
  queued: "#7F8AA0", dialing: "#F2B33D", talking: "#6C93FF", extracting: "#A98BFF", done: "#3DD6A0", failed: "#FF7A7A",
};
const TEXT: Record<BoardState, string> = {
  queued: "#9AA5BA", dialing: "#F2B33D", talking: "#9DB6FF", extracting: "#C2AEFF", done: "#6BE3B9", failed: "#FF9A9A",
};

/**
 * A looping sample run of the swarm: the hero of the home page. Starts from a static, finished frame (so the page is
 * complete without JavaScript or with reduced motion), then replays the whole run on a timer.
 */
export function CallBoard({ className }: { className?: string }) {
  const finalFrame = boardAt(LOOP_MS);
  const [rows, setRows] = useState(finalFrame);
  const [winner, setWinner] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timers: ReturnType<typeof setTimeout>[] = [];
    const play = () => {
      setRows(boardAt(0));
      setWinner(false);
      timers = BOARD_EVENTS.map((e) =>
        setTimeout(() => setRows((prev) => prev.map((r, i) => (i === e.row ? { state: e.state, text: e.text } : r))), e.at),
      );
      timers.push(setTimeout(() => setWinner(true), WINNER_AT));
      timers.push(setTimeout(play, LOOP_MS));
    };
    timers.push(setTimeout(play, 1200));
    return () => timers.forEach(clearTimeout);
  }, []);

  const finished = rows.filter((r) => r.state === "done" || r.state === "failed").length;

  return (
    <figure className={cn("overflow-hidden rounded-[14px] bg-[#0F1B33] text-[#E8ECF4] shadow-[0_30px_60px_-30px_rgba(18,32,58,0.55)]", className)}>
      <figcaption className="border-b border-white/10 px-5 py-4">
        <p className="text-xs text-[#9AA5BA]">You asked</p>
        <p className="mt-1 font-display text-lg leading-snug">{BOARD_QUERY}</p>
      </figcaption>
      <ul aria-label="Sample calls" className="divide-y divide-white/[0.07]">
        {rows.map((row, i) => {
          const isWinner = winner && i === WINNER_ROW;
          return (
            <li key={BOARD_ROWS[i].name} className={cn("relative grid grid-cols-[14px_1fr_auto] items-start gap-x-3 px-5 py-2.5 transition-colors duration-500", isWinner && "bg-[#F2C94C]/[0.11]")}>
              {isWinner && <span className="absolute inset-y-0 left-0 w-[3px] bg-[#F2C94C]" aria-hidden />}
              <span className="relative mt-[7px] flex h-2.5 w-2.5" aria-hidden>
                {(row.state === "dialing" || row.state === "talking") && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: DOT[row.state] }} />
                )}
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ background: DOT[row.state] }} />
              </span>
              <div className="min-w-0">
                <p className="truncate text-[15px] font-medium">{BOARD_ROWS[i].name}</p>
                <p className="truncate text-[13px]" style={{ color: TEXT[row.state] }}>{row.text}</p>
              </div>
              <span className="tabular pt-0.5 text-[13px] text-[#9AA5BA]">{BOARD_ROWS[i].miles.toFixed(1)} mi</span>
            </li>
          );
        })}
      </ul>
      <div
        aria-live="polite"
        className={cn(
          "flex items-center justify-between gap-4 px-5 py-3.5 text-[14px] transition-colors duration-500",
          winner ? "bg-[#F2C94C] font-medium text-[#12203A]" : "bg-white/[0.04] text-[#9AA5BA]",
        )}
      >
        <span>{winner ? WINNER_LINE : "Calling in parallel…"}</span>
        <span className="tabular shrink-0 text-[13px] opacity-80">{finished} of {rows.length} done</span>
      </div>
    </figure>
  );
}