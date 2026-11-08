"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, WifiOff } from "lucide-react";
import { AgentGrid } from "@/components/AgentGrid";
import { CommanderLog } from "@/components/CommanderLog";
import { ComparisonTable } from "@/components/ComparisonTable";
import { RequireAuth } from "@/components/site/RequireAuth";
import { StatsBar } from "@/components/StatsBar";
import { SwarmCanvas } from "@/components/SwarmCanvas";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { WinnerCard } from "@/components/WinnerCard";
import { ApiError, api } from "@/lib/api";
import { isRescue } from "@/lib/copy";
import { inquiryCalls } from "@/lib/reducer";
import { useSwarm } from "@/lib/useSwarm";

export default function SwarmPage({ params }: { params: { id: string } }) {
  const { state, connection, markReserving } = useSwarm(params.id);
  const [pinned, setPinned] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Follow the conversation that is currently happening, unless the user picked one themselves.
  const followed = useMemo(() => {
    const calls = inquiryCalls(state);
    const talking = [...calls].reverse().find((c) => c.state === "talking");
    return (talking ?? [...calls].reverse().find((c) => c.transcript.length > 0) ?? calls[0])?.callId ?? null;
  }, [state]);
  const selectedId = pinned ?? followed;
  const selected = selectedId ? state.calls[selectedId] ?? null : null;
  // Once every call has finished the comparison is the answer, so it moves up above the call cards.
  const finished = Boolean(state.completed);

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
      <Shell>
        <p className="py-24 text-center text-lg">This swarm doesn't exist. It may have been cleared when the server restarted.</p>
      </Shell>
    );
  }

  return (
    <Shell>
      {connection === "unreachable" && <Banner text="Can't reach the server. Check that the backend (or npm run mock) is running." />}
      {connection === "reconnecting" && <Banner text="Connection lost. Reconnecting and catching up." />}

      <h1 className="max-w-3xl text-2xl font-semibold leading-tight sm:text-3xl">
        {!state.query ? "Connecting to the swarm…" : isRescue(state.intent) ? "Finding someone to collect your surplus food" : state.query}
      </h1>
      {state.intent && (
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">
          {isRescue(state.intent) ? state.query : state.intent.summary}
          {state.mode === "simulated" ? ` · Practice run with made-up ${isRescue(state.intent) ? "organizations" : "businesses"}` : ""}
        </p>
      )}

      <div className="mt-5 space-y-4">
        <StatsBar swarm={state} onCancel={cancel} cancelling={cancelling} />
        {actionError && <p role="alert" className="text-sm text-failed">{actionError}</p>}
        <WinnerCard swarm={state} onReserve={reserve} />

        {finished && <ComparisonTable swarm={state} onSelect={setPinned} onReserve={reserve} />}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(340px,1fr)]">
          <AgentGrid swarm={state} selectedCallId={selectedId} onSelect={setPinned} />
          <div className="space-y-4 lg:sticky lg:top-4 lg:self-start">
            <TranscriptPanel swarm={state} call={selected} />
            <CommanderLog swarm={state} />
          </div>
        </div>

        {!finished && <ComparisonTable swarm={state} onSelect={setPinned} onReserve={reserve} />}

        {/* The map is a nice-to-watch extra, so it sits below the calls and results people actually need. */}
        <section aria-label="Call map" className="rounded-panel border border-line bg-card px-4 py-4">
          <h2 className="font-display text-lg font-semibold">Call map</h2>
          <p className="text-xs text-ink-soft">Every business the swarm is calling, coloured by what is happening on that call. Select one to read it.</p>
          <div className="mx-auto mt-2 max-w-md">
            <SwarmCanvas swarm={state} selectedCallId={selectedId} onSelect={setPinned} />
          </div>
        </section>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <Link href="/app" className="mb-5 inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden /> New search
      </Link>
      <RequireAuth>{children}</RequireAuth>
    </main>
  );
}

function Banner({ text }: { text: string }) {
  return (
    <div role="status" className="mb-4 flex items-center gap-2 rounded-md border border-dialing/40 bg-dialing/10 px-3 py-2 text-sm">
      <WifiOff className="h-4 w-4" aria-hidden /> {text}
    </div>
  );
}