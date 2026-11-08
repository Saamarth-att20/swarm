"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";
import { STATE_HEX } from "@/lib/format";
import { inquiryCalls } from "@/lib/reducer";
import type { SwarmView } from "@/lib/types";

const C = 300;
const INNER = 150;
const OUTER = 245;
const PULSE_ORIGIN = { transformBox: "fill-box", transformOrigin: "center" } as const;

interface Props {
  swarm: SwarmView;
  selectedCallId: string | null;
  onSelect: (callId: string) => void;
}

/** Radial map of the swarm: the commander in the middle, one node per business, lines coloured by call state. */
export function SwarmCanvas({ swarm, selectedCallId, onSelect }: Props) {
  const running = swarm.created && !swarm.completed;

  const positions = useMemo(() => {
    const inner = swarm.targetOrder.filter((id) => swarm.targets[id]?.tier === "primary");
    const outer = swarm.targetOrder.filter((id) => swarm.targets[id]?.tier !== "primary");
    const place = (ids: string[], r: number, offset: number) =>
      ids.map((id, i) => {
        const a = ((i + offset) / Math.max(ids.length, 1)) * Math.PI * 2 - Math.PI / 2;
        return [id, { x: C + Math.cos(a) * r, y: C + Math.sin(a) * r }] as const;
      });
    return Object.fromEntries([...place(inner, INNER, 0), ...place(outer, OUTER, 0.5)]);
  }, [swarm.targetOrder, swarm.targets]);

  const bestTarget = swarm.ranked?.bestCallId ? swarm.calls[swarm.ranked.bestCallId]?.targetId : null;
  const arcs = swarm.log.filter((l) => l.kind === "reroute" && l.fromTargetId).slice(-4);

  return (
    <svg viewBox="0 0 600 600" className="h-auto w-full" role="img" aria-label="Map of calls in progress">
      {[INNER, OUTER].map((r) => (
        <circle key={r} cx={C} cy={C} r={r} fill="none" stroke="#CDD3CC" strokeDasharray="2 6" />
      ))}

      {swarm.targetOrder.map((id) => {
        const pos = positions[id];
        const call = swarm.calls[swarm.inquiryByTarget[id]];
        if (!pos) return null;
        const state = call?.state ?? "queued";
        const active = state === "dialing" || state === "talking" || state === "extracting";
        return (
          <line
            key={`l-${id}`}
            x1={C}
            y1={C}
            x2={pos.x}
            y2={pos.y}
            stroke={STATE_HEX[state]}
            strokeWidth={active ? 2.5 : 1.5}
            strokeOpacity={state === "queued" ? 0.18 : active ? 0.95 : 0.45}
            strokeDasharray={active || state === "failed" ? "6 6" : undefined}
            className={active ? "animate-dash" : undefined}
          />
        );
      })}

      {arcs.map((l) => {
        if (l.kind !== "reroute" || !l.fromTargetId) return null;
        const a = positions[l.fromTargetId];
        const b = positions[l.toTargetId];
        if (!a || !b) return null;
        return (
          <motion.path
            key={`arc-${l.seq}`}
            d={`M ${a.x} ${a.y} Q ${C} ${C} ${b.x} ${b.y}`}
            fill="none"
            stroke="#12203A"
            strokeWidth={1.5}
            strokeDasharray="3 5"
            initial={{ pathLength: 0, opacity: 0.9 }}
            animate={{ pathLength: 1, opacity: 0.35 }}
            transition={{ duration: 0.9 }}
          />
        );
      })}

      <g>
        {running && (
          <motion.circle cx={C} cy={C} r={34} fill="none" stroke="#12203A" strokeOpacity={0.25} style={PULSE_ORIGIN} animate={{ scale: [1, 1.8], opacity: [0.6, 0] }} transition={{ duration: 2, repeat: Infinity }} />
        )}
        <circle cx={C} cy={C} r={34} fill="#12203A" />
        <text x={C} y={C - 2} textAnchor="middle" fill="#EEF0EC" fontSize="11" fontWeight="600">
          Commander
        </text>
        <text x={C} y={C + 13} textAnchor="middle" fill="#EEF0EC" fillOpacity={0.7} fontSize="10">
          {inquiryCalls(swarm).length} calls
        </text>
      </g>

      {swarm.targetOrder.map((id, index) => {
        const pos = positions[id];
        const target = swarm.targets[id];
        const call = swarm.calls[swarm.inquiryByTarget[id]];
        if (!pos || !target) return null;
        const state = call?.state ?? "queued";
        const selected = call && call.callId === selectedCallId;
        const isBest = bestTarget === id;
        const color = STATE_HEX[state];
        return (
          <motion.g
            key={id}
            initial={{ x: C, y: C, opacity: 0 }}
            animate={{ x: pos.x, y: pos.y, opacity: 1 }}
            transition={{ type: "spring", stiffness: 120, damping: 18 }}
            onClick={() => call && onSelect(call.callId)}
            style={{ cursor: call ? "pointer" : "default" }}
            tabIndex={call ? 0 : -1}
            role="button"
            aria-label={`${target.name}: ${state}`}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && call && onSelect(call.callId)}
          >
            {state === "talking" && (
              <motion.circle r={14} fill="none" stroke={color} strokeWidth={2} style={PULSE_ORIGIN} animate={{ scale: [1, 1.9], opacity: [0.7, 0] }} transition={{ duration: 1.4, repeat: Infinity }} />
            )}
            {isBest && <circle r={21} fill="none" stroke="#F2C94C" strokeWidth={4} />}
            {selected && <circle r={19} fill="none" stroke="#12203A" strokeWidth={1.5} />}
            <circle r={13} fill={state === "queued" ? "#F8F9F6" : color} stroke={color} strokeWidth={2} />
            <text textAnchor="middle" dy="0.35em" fontSize="11" fontWeight="700" fill={state === "queued" ? "#8A93A3" : "#fff"}>
              {index + 1}
            </text>
            <title>{`${target.name} — ${state}`}</title>
          </motion.g>
        );
      })}
    </svg>
  );
}
