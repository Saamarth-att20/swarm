"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

const NODES = [
  { x: 50, y: 8, name: "Willow Street Pharmacy", state: "Connected" },
  { x: 70, y: 14, name: "Northline Community Drugs", state: "Ringing" },
  { x: 87, y: 31, name: "Hearthside Pharmacy", state: "Connected" },
  { x: 91, y: 55, name: "Juniper Care Pharmacy", state: "Listening" },
  { x: 78, y: 77, name: "Alder Family Pharmacy", state: "Ringing" },
  { x: 58, y: 91, name: "Market Square Pharmacy", state: "Connected" },
  { x: 35, y: 87, name: "Eastgate Drug & Wellness", state: "Listening" },
  { x: 14, y: 72, name: "Cedar Hill Pharmacy", state: "Connected" },
  { x: 8, y: 48, name: "Harbor Health Pharmacy", state: "Ringing" },
  { x: 18, y: 24, name: "Oak & Pine Pharmacy", state: "Connected" },
  { x: 35, y: 11, name: "Mission Community Pharmacy", state: "Listening" },
  { x: 57, y: 38, name: "Parkside Family Pharmacy", state: "Best answer" },
];
const COUNT = NODES.length;
const BEST = COUNT - 1;

const STEP = 380; // gap between one line starting and the next
const ARRIVE = 560; // how long a line takes to reach its number
const HOLD = 4200; // pause on the finished diagram before it replays

const blank = () => Array<boolean>(COUNT).fill(false);
const full = () => Array<boolean>(COUNT).fill(true);
const mark = (list: boolean[], i: number) => list.map((v, k) => (k === i ? true : v));

function shuffled() {
  const order = Array.from({ length: COUNT }, (_, i) => i);
  for (let i = COUNT - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

/** The twelve-caller diagram: lines draw out from the Commander to each number in a random order, then replay. */
export function Constellation({ className = "" }: { className?: string }) {
  const wrapRef = useRef<HTMLElement>(null);
  const [lit, setLit] = useState<boolean[]>(blank);
  const [awake, setAwake] = useState<boolean[]>(blank);
  const [hovered, setHovered] = useState<number | null>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [visible, setVisible] = useState(false);

  // Only start once the diagram scrolls into view.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setLit(full());
      setAwake(full());
      return;
    }
    if (!visible) return;

    const timers: ReturnType<typeof setTimeout>[] = [];
    const later = (fn: () => void, ms: number) => {
      timers.push(setTimeout(fn, ms));
    };

    const run = () => {
      const order = shuffled();
      setLit(blank());
      setAwake(blank());
      order.forEach((idx, k) => {
        later(() => setLit((p) => mark(p, idx)), 60 + k * STEP);
        later(() => setAwake((p) => mark(p, idx)), 60 + k * STEP + ARRIVE);
      });
      const end = 60 + (COUNT - 1) * STEP + ARRIVE;
      later(run, end + HOLD);
    };
    run();
    return () => timers.forEach(clearTimeout);
  }, [visible]);

  const live = awake.filter(Boolean).length;
  const active = hovered ?? BEST; // the best answer stays highlighted until you hover another number
  const current = hovered === null ? null : NODES[hovered];

  return (
    <section
      ref={wrapRef}
      className={`constellation-wrap ${className}`}
      onPointerMove={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setTilt({
          x: (event.clientX - rect.left) / rect.width - 0.5,
          y: (event.clientY - rect.top) / rect.height - 0.5,
        });
      }}
      onPointerLeave={() => {
        setHovered(null);
        setTilt({ x: 0, y: 0 });
      }}
      aria-label="Diagram showing twelve AI callers working in parallel"
    >
      <div
        className="constellation"
        style={{ "--tilt-x": `${tilt.x * 12}px`, "--tilt-y": `${tilt.y * 12}px` } as CSSProperties}
      >
        <span className="orbit orbit-one" />
        <span className="orbit orbit-two" />
        <span className="orbit orbit-three" />
        <svg className="constellation-lines" viewBox="0 0 100 100" aria-hidden="true">
          {NODES.map((node, i) => (
            <g key={node.name} className={`${lit[i] ? "lit" : ""} ${active === i ? "active" : ""}`}>
              <line className="track" x1="50" y1="50" x2={node.x} y2={node.y} />
              <line className="beam" x1="50" y1="50" x2={node.x} y2={node.y} pathLength={1} />
              <circle className="signal" cx={node.x} cy={node.y} r=".75" />
            </g>
          ))}
        </svg>
        <div className="commander-core">
          <span className="core-ripple" />
          <span className="core-label">Commander</span>
          <strong>{live}</strong>
          <small>calls live</small>
        </div>
        {NODES.map((node, i) => (
          <button
            key={node.name}
            type="button"
            className={`constellation-node ${awake[i] ? "awake" : ""} ${active === i ? "active" : ""}`}
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            onPointerEnter={() => setHovered(i)}
            onPointerLeave={() => setHovered(null)}
            onFocus={() => setHovered(i)}
            onBlur={() => setHovered(null)}
            onClick={() => setHovered(i)}
            aria-label={`${node.name}, ${node.state}`}
          >
            <span>{i + 1}</span>
          </button>
        ))}
        {current && hovered !== null && (
          <div
            className={`node-detail ${hovered === BEST ? "up" : current.x > 60 ? "flip" : ""}`}
            style={{ left: `${current.x}%`, top: `${current.y}%` }}
          >
            <span>{current.state}</span>
            <strong>{current.name}</strong>
            <small>{hovered === BEST ? "“Yes, we have it in stock.”" : "Caller checking availability now"}</small>
          </div>
        )}
        <div className="network-status">
          <span className="network-wave">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>{live < COUNT ? "Connecting the swarm" : "Twelve calls. One clear answer."}</span>
        </div>
      </div>
    </section>
  );
}