"use client";

import { useEffect, useState } from "react";
import { CircleSlash, PhoneCall, PhoneOff, Search, Square, Timer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { counts } from "@/lib/reducer";
import { copyFor } from "@/lib/copy";
import { elapsed } from "@/lib/format";
import type { SwarmView } from "@/lib/types";

function Stat({ icon: Icon, value, label, tone }: { icon: typeof Timer; value: string | number; label: string; tone?: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <Icon className={`h-4 w-4 ${tone ?? "text-ink-faint"}`} aria-hidden />
      <div>
        <div className="font-display text-xl font-semibold leading-none tabular">{value}</div>
        <div className="mt-1 text-xs text-ink-soft">{label}</div>
      </div>
    </div>
  );
}

export function StatsBar({ swarm, onCancel, cancelling }: { swarm: SwarmView; onCancel: () => void; cancelling: boolean }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const running = swarm.created && !swarm.completed;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 500);
    return () => clearInterval(t);
  }, [running]);

  const k = counts(swarm);
  const seconds = swarm.completed ? swarm.completed.elapsed_s : swarm.startedAt ? now - swarm.startedAt : 0;

  return (
    <div className="flex flex-wrap items-stretch divide-x divide-line rounded-panel border border-line bg-card">
      <Stat icon={Timer} value={elapsed(seconds)} label="elapsed" />
      <Stat icon={PhoneCall} value={k.active} label="on the line" tone={k.active ? "text-talking" : undefined} />
      <Stat icon={Search} value={k.matches} label={copyFor(swarm.intent).matches} tone={k.matches ? "text-done" : undefined} />
      <Stat icon={PhoneOff} value={k.failed} label="no answer / failed" tone={k.failed ? "text-failed" : undefined} />
      <Stat icon={CircleSlash} value={`${k.done + k.failed}/${k.total}`} label="calls finished" />
      {running && (
        <div className="ml-auto flex items-center px-4">
          <Button variant="danger" size="sm" onClick={onCancel} disabled={cancelling}>
            <Square className="h-3.5 w-3.5" aria-hidden /> {cancelling ? "Stopping" : "Stop swarm"}
          </Button>
        </div>
      )}
    </div>
  );
}
