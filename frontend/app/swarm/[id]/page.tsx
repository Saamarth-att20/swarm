"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, WifiOff } from "lucide-react";
import { AgentGrid } from "@/components/AgentGrid";
import { CommanderLog } from "@/components/CommanderLog";
import { ComparisonTable } from "@/components/ComparisonTable";
import { Icon } from "@/components/design/Icon";
import { RequireAuth } from "@/components/site/RequireAuth";
import { SiteNav } from "@/components/site/SiteNav";
import { StatsBar } from "@/components/StatsBar";
import { SwarmCanvas } from "@/components/SwarmCanvas";
import { WinnerCard } from "@/components/WinnerCard";
import { ApiError, api } from "@/lib/api";
import { completionNote, headline, subtitle } from "@/lib/callDisplay";
import { useSwarm } from "@/lib/useSwarm";

export default function SwarmPage({ params }: { params: { id: string } }) {
  const { state, connection, markReserving } = useSwarm(params.id);
  const [expanded, setExpanded] = useState<string | null>(null); // the caller whose full conversation is open
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Once every call has finished the comparison is the answer, so it moves up above the call cards.
  const finished = Boolean(state.completed);
  const running = state.created && !finished;
  const note = completionNote(state);

  function toggle(callId: string) {
    setExpanded((current) => (current === callId ? null : callId));
  }

  /** From the table or the map: open that caller's conversation and bring it into view. Only ever runs on a click. */
  function openCall(callId: string) {
    setExpanded(callId);
    requestAnimationFrame(() => document.getElementById(`call-${callId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  async function cancel() {
    setCancelling(true);
    try {
      await api.cancel(params.id);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't stop the swarm.");
      setCancelling(false);
    }
  }

  async function reserve(callId: string) {
    setActionError(null);
    try {
      markReserving(callId); // cleared by the swarm.reserved event
      await api.reserve(params.id, callId);
    } catch (e) {
      markReserving(null);
      setActionError(e instanceof ApiError ? e.message : "Couldn't start the reservation.");
    }
  }

  if (connection === "not_found") {
    return (
      <>
        <SiteNav current="app" />
        <RequireAuth>
          <main className="live-shell route-view">
            <p className="page-empty">This swarm doesn't exist. It may have been cleared when the server restarted.</p>
          </main>
        </RequireAuth>
      </>
    );
  }

  return (
    <>
      <SiteNav current="app" />
      <RequireAuth>
        <main className={`live-shell route-view ${finished ? "results-page" : ""}`}>
          {connection === "unreachable" && <Banner text="Can't reach the server. Check that the backend (or npm run mock) is running." />}
          {connection === "reconnecting" && <Banner text="Connection lost. Reconnecting and catching up." />}

          <div className="live-meta">
            <Link href="/app" className="back">
              <ArrowLeft className="h-4 w-4" aria-hidden /> New search
            </Link>
            {note && (
              <span className="complete-label">
                <Icon name="check" size={14} /> {note}
              </span>
            )}
          </div>

          <div className="live-title">
            <div>
              <h1>{headline(state)}</h1>
              {state.query && <p>{subtitle(state)}</p>}
            </div>
            {running && (
              <div className="live-actions">
                <span className="live-indicator">
                  <i /> Swarm in progress
                </span>
                <button type="button" className="btn secondary small" onClick={cancel} disabled={cancelling}>
                  {cancelling ? "Stopping…" : "Stop swarm"}
                </button>
              </div>
            )}
          </div>

          <StatsBar swarm={state} />
          {actionError && (
            <p role="alert" className="page-error">
              {actionError}
            </p>
          )}

          <WinnerCard swarm={state} onReserve={reserve} />
          {finished && <ComparisonTable swarm={state} onSelect={openCall} onReserve={reserve} />}
          <AgentGrid swarm={state} expandedCallId={expanded} onToggle={toggle} />
          {!finished && <ComparisonTable swarm={state} onSelect={openCall} onReserve={reserve} />}

          <div className="lower-grid">
            <CommanderLog swarm={state} />
            {/* The map is a nice-to-watch extra, so it sits at the bottom, below the calls and results people actually need. */}
            <section className="panel" aria-label="Call map">
              <div className="section-row">
                <h2>Call map</h2>
              </div>
              <p className="panel-note">Every business the swarm is calling, coloured by what is happening on that call. Select one to read it.</p>
              <div className="map-wrap">
                <SwarmCanvas swarm={state} selectedCallId={expanded} onSelect={openCall} />
              </div>
            </section>
          </div>
        </main>
      </RequireAuth>
    </>
  );
}

function Banner({ text }: { text: string }) {
  return (
    <div role="status" className="live-banner">
      <WifiOff className="h-4 w-4" aria-hidden /> {text}
    </div>
  );
}