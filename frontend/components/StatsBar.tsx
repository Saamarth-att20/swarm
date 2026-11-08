"use client";

import { useEffect, useState } from "react";
import { clock } from "@/lib/callDisplay";
import { copyFor } from "@/lib/copy";
import { counts } from "@/lib/reducer";
import type { SwarmView } from "@/lib/types";

/** The dark bar under the title: how far along the swarm is. The stop button lives in the page header. */
export function StatsBar({ swarm }: { swarm: SwarmView }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const running = swarm.created && !swarm.completed;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 500);
    return () => clearInterval(t);
  }, [running]);

  const k = counts(swarm);
  const finished = k.done + k.failed;
  const seconds = swarm.completed ? swarm.completed.elapsed_s : swarm.startedAt ? now - swarm.startedAt : 0;
  const matchesLabel = copyFor(swarm.intent).matches;
  const pct = k.total > 0 ? Math.round((finished / k.total) * 100) : 0;

  return (
    <div className="stats four" role="group" aria-label="Swarm progress">
      <div>
        <span>Calls finished</span>
        <strong>
          {finished}
          <small>/ {k.total}</small>
        </strong>
      </div>
      <div>
        <span>On the line</span>
        <strong>{k.active}</strong>
      </div>
      <div>
        <span>{matchesLabel.charAt(0).toUpperCase() + matchesLabel.slice(1)}</span>
        <strong className="green">{k.matches}</strong>
      </div>
      <div>
        <span>Elapsed time</span>
        <strong>{clock(seconds)}</strong>
      </div>
      <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Calls finished">
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}