// The ring of eight dots (the swarm). Positions and the slow spin come from design.css. Author: Saamarth Attray
import type { CSSProperties } from "react";

export function DotRing() {
  return (
    <span className="dot-ring" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <i key={i} style={{ "--i": i } as CSSProperties} />
      ))}
    </span>
  );
}