"use client";

import { Check, Loader2, Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { copyFor, isRescue } from "@/lib/copy";
import { availabilityLabel, miles, money } from "@/lib/format";
import { inquiryCalls } from "@/lib/reducer";
import type { CallView, SwarmView } from "@/lib/types";

interface Row {
  call: CallView;
  rank: number | null;
  reasons: string[];
}

function rows(swarm: SwarmView): Row[] {
  const ranked = new Map((swarm.ranked?.rankings ?? []).map((r) => [r.call_id, r]));
  const out = inquiryCalls(swarm)
    .filter((c) => c.result)
    .map((call) => ({ call, rank: ranked.get(call.callId)?.rank ?? null, reasons: ranked.get(call.callId)?.reasons ?? [] }));
  const order = { yes: 0, partial: 1, unknown: 2, no: 3 } as const;
  const sooner = (c: CallView) => c.result!.wait_minutes ?? c.result!.price ?? 1e9;
  return out.sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99) || order[a.call.result!.available] - order[b.call.result!.available] || sooner(a.call) - sooner(b.call));
}

const Tri = ({ value, yes, no }: { value: boolean | null | undefined; yes: string; no: string }) =>
  value === true ? <Check className="h-4 w-4 text-done" aria-label={yes} /> : value === false ? <X className="h-4 w-4 text-ink-faint" aria-label={no} /> : <span>—</span>;

export function ComparisonTable({ swarm, onSelect, onReserve }: { swarm: SwarmView; onSelect: (id: string) => void; onReserve: (callId: string) => void }) {
  const data = rows(swarm);
  const rescue = isRescue(swarm.intent);
  const copy = copyFor(swarm.intent);
  const kind = swarm.intent?.kind ?? "product";
  const isProduct = kind === "product";
  const best = swarm.ranked?.bestCallId;
  const canReserve = Boolean(swarm.completed) && !swarm.reserved;

  return (
    <section className="rounded-panel border border-line bg-card" aria-label="Comparison">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="font-display text-lg font-semibold">{rescue ? "Who can collect it" : "Comparison"}</h2>
        <p className="text-xs text-ink-soft">{swarm.ranked ? swarm.ranked.criteria : "Rows appear as each call reports back."}</p>
      </header>
      {data.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-ink-faint">No answers yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs text-ink-soft">
              <tr className="border-b border-line">
                <th className="px-4 py-2 font-medium">{rescue ? "Organization" : "Business"}</th>
                <th className="px-3 py-2 font-medium">Answer</th>
                {!rescue && <th className="px-3 py-2 text-right font-medium">Price</th>}
                <th className="px-3 py-2 text-right font-medium">{rescue ? copy.whenColumn : isProduct ? "In stock" : copy.whenColumn}</th>
                <th className="px-3 py-2 font-medium">{rescue ? "Fresh food" : "Hold"}</th>
                <th className="px-3 py-2 text-right font-medium">Distance</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.map(({ call, rank, reasons }) => {
                const r = call.result!;
                const target = swarm.targets[call.targetId];
                const isBest = call.callId === best;
                const positive = r.available === "yes" || (r.available === "partial" && !(rescue && r.can_pickup === false));
                const reservedHere = swarm.reserved?.call_id === call.callId;
                return (
                  <tr key={call.callId} onClick={() => onSelect(call.callId)} className={cn("cursor-pointer border-b border-line last:border-0 hover:bg-ink/[0.03]", isBest && "bg-[#FBF2CC] hover:bg-[#FBF2CC]", !positive && "text-ink-soft")}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 font-medium">
                        {isBest && <Star className="h-3.5 w-3.5 fill-best text-[#B8901A]" aria-label={copy.bestTitle} />}
                        {rank ? <span className="tabular text-ink-faint">{rank}.</span> : null}
                        {target.name}
                      </div>
                      {isBest && reasons.length > 0 && <div className="mt-0.5 text-xs font-normal text-ink-soft">{reasons.slice(0, 3).join(" · ")}</div>}
                    </td>
                    <td className="px-3 py-3">{availabilityLabel(r, kind)}</td>
                    {!rescue && <td className="tabular px-3 py-3 text-right">{money(r.price)}</td>}
                    <td className="tabular px-3 py-3 text-right">{rescue || !isProduct ? copy.whenValue(r.wait_minutes) : r.quantity ?? "—"}</td>
                    <td className="px-3 py-3">{rescue ? <Tri value={r.perishables_ok} yes="Takes fresh food" no="No fresh food" /> : <Tri value={r.can_hold} yes="Can hold" no="Won't hold" />}</td>
                    <td className="tabular px-3 py-3 text-right">{miles(target.distance_miles)}</td>
                    <td className="px-4 py-2 text-right">
                      {positive && (
                        <Button
                          size="sm"
                          variant={isBest ? "primary" : "secondary"}
                          disabled={!canReserve || swarm.reserving !== null}
                          onClick={(e) => {
                            e.stopPropagation();
                            onReserve(call.callId);
                          }}
                        >
                          {swarm.reserving === call.callId ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
                          {reservedHere ? (rescue ? "Confirmed" : "Reserved") : swarm.reserving === call.callId ? (rescue ? "Confirming" : "Reserving") : rescue ? "Confirm" : "Reserve"}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
