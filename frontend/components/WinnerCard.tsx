"use client";

import { Icon } from "@/components/design/Icon";
import { bestSoFar, directionsHref, telHref } from "@/lib/callDisplay";
import { copyFor, isRescue } from "@/lib/copy";
import { availabilityLabel, miles, money, resultLine, waitLabel } from "@/lib/format";
import type { SwarmView } from "@/lib/types";

/** The answer. While calls are still running it shows the best one so far; once finished, the ranked winner with Reserve. */
export function WinnerCard({ swarm, onReserve }: { swarm: SwarmView; onReserve: (callId: string) => void }) {
  const copy = copyFor(swarm.intent);
  const rescue = isRescue(swarm.intent);
  const done = Boolean(swarm.completed);
  const call = done ? (swarm.ranked?.bestCallId ? swarm.calls[swarm.ranked.bestCallId] : null) : bestSoFar(swarm);

  if (!done && !call) return null;

  if (!call || !call.result) {
    const stopped = swarm.completed?.status === "cancelled";
    return (
      <section className="winner-card empty" aria-label="Result">
        <span className="winner-mark muted">
          <Icon name="close" size={22} />
        </span>
        <div className="winner-copy">
          <h2>{stopped ? "Swarm stopped" : copy.noWinnerTitle}</h2>
          <p>{stopped ? "You stopped the swarm before a best match was found." : copy.noWinnerBody(swarm.completed?.calls_made ?? 0)}</p>
        </div>
      </section>
    );
  }

  const target = swarm.targets[call.targetId];
  const r = call.result;
  const reserved = swarm.reserved && swarm.reserved.call_id === call.callId ? swarm.reserved : null;
  const kind = swarm.intent?.kind ?? "product";
  const detail = rescue
    ? `${availabilityLabel(r, kind)} · ${copy.whenValue(r.wait_minutes).replace(/^~/, "in ~")} · ${r.perishables_ok ? "takes fresh food · " : ""}${miles(target.distance_miles)} away`
    : `${availabilityLabel(r, kind)} · ${money(r.price)} · ${kind === "product" ? (r.quantity != null ? `${r.quantity} in stock` : "in stock") : `arrives in ${waitLabel(r.wait_minutes)}`} · ${miles(target.distance_miles)} away`;
  const reasons = done && !rescue ? swarm.ranked?.rankings.find((x) => x.call_id === call.callId)?.reasons.join(". ") : "";
  const where = [target.phone, target.address, r.hours].filter(Boolean).join(" · ");
  const label = done ? copy.bestTitle : `${copy.bestTitle} so far`;

  return (
    <section className="winner-card" aria-label={label}>
      <span className="winner-mark">
        <Icon name="check" size={24} />
      </span>
      <div className="winner-copy">
        <span className="best-label">{label}</span>
        <h2>{target.name}</h2>
        <p>{detail}</p>
        {reasons && <p className="winner-reasons">{reasons}</p>}
        {where && <span className="winner-meta">{where}</span>}
      </div>
      <div className="winner-actions">
        {reserved ? (
          <span className={`winner-reserved ${reserved.success ? "ok" : "fail"}`}>
            <Icon name={reserved.success ? "check" : "close"} size={18} />
            {reserved.success ? copy.reservedOk : copy.reservedFail}
          </span>
        ) : (
          done && (
            <button type="button" className="btn dark" onClick={() => onReserve(call.callId)} disabled={swarm.reserving !== null}>
              {swarm.reserving ? <span className="spinner" /> : null}
              <span>{swarm.reserving ? copy.reserving : copy.reserve}</span>
            </button>
          )
        )}
        {target.phone && (
          <a className="btn secondary" href={telHref(target.phone)}>
            <span>Call them</span>
            <Icon name="phone" size={17} />
          </a>
        )}
        <a className="btn secondary" href={directionsHref(target.lat, target.lng)} target="_blank" rel="noopener noreferrer">
          <span>Get directions</span>
          <Icon name="route" size={17} />
        </a>
      </div>
      {reserved?.confirmation && (
        <p className="winner-note">
          Confirmation: <strong>{reserved.confirmation}</strong>
        </p>
      )}
      {reserved && <p className="winner-note">{reserved.message}</p>}
      {!reserved && <p className="sr-only">{resultLine(r, kind)}</p>}
    </section>
  );
}