"use client";

import { Star } from "lucide-react";
import { Icon } from "@/components/design/Icon";
import { isPositive } from "@/lib/callDisplay";
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
  value === true ? <Icon name="check" size={16} /> : value === false ? <span aria-label={no}>No</span> : <span aria-label="Not said">—</span>;

/** Every answer so far, best first. Appears as soon as the first call reports back. */
export function ComparisonTable({ swarm, onSelect, onReserve }: { swarm: SwarmView; onSelect: (id: string) => void; onReserve: (callId: string) => void }) {
  const data = rows(swarm);
  if (data.length === 0) return null;
  const rescue = isRescue(swarm.intent);
  const copy = copyFor(swarm.intent);
  const kind = swarm.intent?.kind ?? "product";
  const isProduct = kind === "product";
  const best = swarm.ranked?.bestCallId;
  const canReserve = Boolean(swarm.completed) && !swarm.reserved;

  return (
    <section className="comparison" aria-label="Comparison">
      <div className="section-row">
        <h2>{rescue ? "Who can collect it" : "All results"}</h2>
        <span>{swarm.ranked ? swarm.ranked.criteria : "Rows appear as each call reports back."}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{rescue ? "Organization" : "Business"}</th>
              <th className="num">Distance</th>
              <th>Answer</th>
              {!rescue && <th className="num">Price</th>}
              <th className="num">{rescue ? copy.whenColumn : isProduct ? "In stock" : copy.whenColumn}</th>
              <th>{rescue ? "Fresh food" : "Hold"}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.map(({ call, rank, reasons }) => {
              const r = call.result!;
              const target = swarm.targets[call.targetId];
              const isBest = call.callId === best;
              const positive = isPositive(r, kind);
              const reservedHere = swarm.reserved?.call_id === call.callId;
              return (
                <tr key={call.callId} className={cn("row-link", isBest && "best-row")} onClick={() => onSelect(call.callId)}>
                  <td>
                    <div className="biz-cell">
                      <span className={cn("rank", isBest && "win")}>{isBest ? <Icon name="check" size={12} /> : rank ?? "·"}</span>
                      <div>
                        <strong>
                          {target.name}
                          {isBest && <Star className="ml-1.5 inline h-3.5 w-3.5 fill-best text-[#B8901A]" aria-label={copy.bestTitle} />}
                        </strong>
                        {isBest && reasons.length > 0 && <small className="row-reasons">{reasons.slice(0, 3).join(" · ")}</small>}
                      </div>
                    </div>
                  </td>
                  <td className="num">{miles(target.distance_miles)}</td>
                  <td>
                    <span className={cn("answer", !positive && "closed")}>{availabilityLabel(r, kind)}</span>
                  </td>
                  {!rescue && <td className="num">{money(r.price)}</td>}
                  <td className="num">{rescue || !isProduct ? copy.whenValue(r.wait_minutes) : r.quantity ?? "—"}</td>
                  <td>{rescue ? <Tri value={r.perishables_ok} yes="Takes fresh food" no="No fresh food" /> : <Tri value={r.can_hold} yes="Can hold" no="Won't hold" />}</td>
                  <td className="num">
                    {positive && (
                      <button
                        type="button"
                        className={cn("btn small", isBest ? "dark" : "secondary")}
                        disabled={!canReserve || swarm.reserving !== null}
                        onClick={(e) => {
                          e.stopPropagation();
                          onReserve(call.callId);
                        }}
                      >
                        {swarm.reserving === call.callId ? <span className="spinner" /> : null}
                        {reservedHere ? (rescue ? "Confirmed" : "Reserved") : swarm.reserving === call.callId ? (rescue ? "Confirming" : "Reserving") : rescue ? "Confirm" : "Reserve"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}