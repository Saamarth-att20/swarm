"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Loader2, Phone, Star, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { copyFor, isRescue } from "@/lib/copy";
import { availabilityLabel, miles, money, resultLine, waitLabel } from "@/lib/format";
import type { SwarmView } from "@/lib/types";

export function WinnerCard({ swarm, onReserve }: { swarm: SwarmView; onReserve: (callId: string) => void }) {
  if (!swarm.completed) return null;
  const copy = copyFor(swarm.intent);
  const rescue = isRescue(swarm.intent);
  const bestId = swarm.ranked?.bestCallId;
  const call = bestId ? swarm.calls[bestId] : null;

  if (!call || !call.result) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-panel border border-line bg-card p-5">
        <h2 className="font-display text-xl font-semibold">{swarm.completed.status === "cancelled" ? "Swarm stopped" : copy.noWinnerTitle}</h2>
        <p className="mt-1 max-w-prose text-sm text-ink-soft">
          {swarm.completed.status === "cancelled" ? "You stopped the swarm before a best match was found." : copy.noWinnerBody(swarm.completed.calls_made)}
        </p>
      </motion.div>
    );
  }

  const target = swarm.targets[call.targetId];
  const r = call.result;
  const reserved = swarm.reserved && swarm.reserved.call_id === call.callId ? swarm.reserved : null;
  const kind = swarm.intent?.kind ?? "product";
  const detail = rescue
    ? `${availabilityLabel(r, kind)} · ${copy.whenValue(r.wait_minutes).replace(/^~/, "in ~")} · ${r.perishables_ok ? "takes fresh food · " : ""}${miles(target.distance_miles)} away`
    : `${availabilityLabel(r, kind)} · ${money(r.price)} · ${kind === "product" ? (r.quantity != null ? `${r.quantity} in stock` : "in stock") : `arrives in ${waitLabel(r.wait_minutes)}`} · ${miles(target.distance_miles)} away`;

  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 140, damping: 18 }} className="overflow-hidden rounded-panel border-2 border-best bg-[#FBF2CC]" aria-label={copy.bestTitle}>
      <div className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium text-[#7A5D0A]">
            <Star className="h-4 w-4 fill-best" aria-hidden /> {copy.bestTitle}
          </div>
          <h2 className="mt-1 font-display text-3xl font-semibold leading-tight">{target.name}</h2>
          <p className="mt-1 text-sm text-ink-soft">{detail}</p>
          {swarm.ranked && !rescue && <p className="mt-2 text-sm">{swarm.ranked.rankings.find((x) => x.call_id === call.callId)?.reasons.join(". ")}</p>}
          {target.phone && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-ink-soft">
              <Phone className="h-3.5 w-3.5" aria-hidden /> {target.phone}
              {target.address ? ` · ${target.address}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          {reserved ? (
            <div className={`flex items-center gap-2 text-sm font-medium ${reserved.success ? "text-done" : "text-failed"}`}>
              {reserved.success ? <CheckCircle2 className="h-5 w-5" aria-hidden /> : <XCircle className="h-5 w-5" aria-hidden />}
              {reserved.success ? copy.reservedOk : copy.reservedFail}
            </div>
          ) : (
            <Button onClick={() => onReserve(call.callId)} disabled={swarm.reserving !== null}>
              {swarm.reserving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
              {swarm.reserving ? copy.reserving : copy.reserve}
            </Button>
          )}
          {reserved?.confirmation && <p className="text-sm">Confirmation: <span className="font-semibold tabular">{reserved.confirmation}</span></p>}
        </div>
      </div>
      {reserved && <p className="border-t border-best/60 bg-white/40 px-5 py-2.5 text-sm">{reserved.message}</p>}
      {!reserved && <p className="sr-only">{resultLine(r, kind)}</p>}
    </motion.section>
  );
}
