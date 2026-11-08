"use client";

// The animated "call board": eight made-up pharmacies being dialed in parallel. Author: Saamarth Attray
import { useEffect, useState } from "react";
import { StatusDot, type Status } from "@/components/design/StatusDot";
import { Wave } from "@/components/design/Wave";

const BUSINESSES: { name: string; distance: string; quote: string; final: Status }[] = [
  { name: "Willow Street Pharmacy", distance: "0.8 mi", quote: "Yes, we have it. We can hold it for 30 minutes.", final: "found" },
  { name: "Northline Community Drugs", distance: "1.4 mi", quote: "Let me check the shelf.", final: "talking" },
  { name: "Hearthside Pharmacy", distance: "1.9 mi", quote: "We have the generic in stock.", final: "found" },
  { name: "Juniper Care Pharmacy", distance: "2.2 mi", quote: "One moment while I check.", final: "talking" },
  { name: "Alder Family Pharmacy", distance: "2.8 mi", quote: "We closed at 8.", final: "closed" },
  { name: "Market Square Pharmacy", distance: "3.1 mi", quote: "Calling the pharmacy desk now.", final: "calling" },
  { name: "Eastgate Drug & Wellness", distance: "3.7 mi", quote: "Still checking with the pharmacist.", final: "talking" },
  { name: "Cedar Hill Pharmacy", distance: "4.2 mi", quote: "Sorry, we’re out until tomorrow.", final: "closed" },
];

const LAST_PHASE = 9;

/** `animate` loops the sample run; `compact` is the smaller version for side panels. Reduced motion shows the finished state. */
export function SampleBoard({ animate = true, compact = false }: { animate?: boolean; compact?: boolean }) {
  const [phase, setPhase] = useState(animate ? 0 : LAST_PHASE);

  useEffect(() => {
    if (!animate) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setPhase(LAST_PHASE);
      return;
    }
    const timer = setInterval(() => setPhase((p) => (p >= LAST_PHASE ? 0 : p + 0.5)), 800);
    return () => clearInterval(timer);
  }, [animate]);

  const rows = BUSINESSES.map((b, i) => {
    let status: Status = "standby";
    if (phase > i * 0.7) status = "calling";
    if (phase > i * 0.7 + 1.2) status = i % 3 === 1 ? "talking" : b.final;
    return { ...b, status };
  });
  const done = rows.filter((r) => r.status === "found" || r.status === "closed").length;

  return (
    <div className={`call-board ${compact ? "compact" : ""}`}>
      <div className="board-top">
        <div>
          <span className="sample-label">A sample run with made-up businesses</span>
          <h3>
            Pharmacy that has children’s
            <br />
            amoxicillin in stock right now
          </h3>
        </div>
        <span className="live-pill">
          <i /> Live
        </span>
      </div>
      <div className="board-rows">
        {rows.map((row, i) => (
          <div
            className={`call-row ${row.status} ${row.status === "found" && i === 0 ? "winner-row" : ""}`}
            key={row.name}
          >
            <StatusDot status={row.status} />
            <div className="business">
              <strong>{row.name}</strong>
              <span>{row.status === "standby" ? "Waiting to call" : row.status === "calling" ? "Ringing…" : row.quote}</span>
            </div>
            {row.status === "talking" && <Wave />}
            <span className="distance">{row.distance}</span>
          </div>
        ))}
      </div>
      <div className="board-foot">
        <span>
          <i className="pulse" /> Calling in parallel… {done} of 8 done
        </span>
        <span>00:{String(Math.min(Math.round(phase * 2), 59)).padStart(2, "0")}</span>
      </div>
    </div>
  );
}