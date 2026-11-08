"use client";

import { useEffect, useState } from "react";
import { SwarmCanvas } from "@/components/SwarmCanvas";
import { initialSwarm } from "@/lib/reducer";
import type { CallState, SwarmView, Target } from "@/lib/types";

const CYCLE: CallState[] = ["dialing", "talking", "extracting", "completed"];

function build(states: CallState[]): SwarmView {
  const s = initialSwarm("hero");
  states.forEach((state, i) => {
    const id = `h${i}`;
    const target: Target = { id, name: `Business ${i + 1}`, lat: 0, lng: 0, distance_miles: 1, tier: i < 9 ? "primary" : "backup", source: "mock" };
    s.targets[id] = target;
    s.targetOrder.push(id);
    s.calls[`c${i}`] = { callId: `c${i}`, targetId: id, role: "inquiry", state, reason: null, result: null, transcript: [] };
    s.inquiryByTarget[id] = `c${i}`;
  });
  s.created = true;
  return s;
}

/** Decorative, looping preview of a swarm for the landing page (no server involved). */
export function HeroSwarm() {
  const [states, setStates] = useState<CallState[]>(() => Array.from({ length: 14 }, (_, i) => (i < 9 ? CYCLE[i % 3] : "queued")));
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => {
      setStates((prev) => {
        const next = [...prev];
        const i = Math.floor(Math.random() * next.length);
        const cur = next[i];
        next[i] = cur === "queued" ? "dialing" : cur === "completed" ? (Math.random() < 0.3 ? "failed" : "queued") : cur === "failed" ? "queued" : CYCLE[CYCLE.indexOf(cur) + 1];
        return next;
      });
    }, 650);
    return () => clearInterval(t);
  }, []);
  return <SwarmCanvas swarm={build(states)} selectedCallId={null} onSelect={() => {}} />;
}
