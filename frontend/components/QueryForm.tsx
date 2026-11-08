"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Loader2, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModePicker, type CallMode } from "@/components/ModePicker";
import { useCapabilities } from "@/lib/useCapabilities";
import { ApiError, api } from "@/lib/api";
import type { CreateSwarmRequest } from "@/lib/types";

const EXAMPLES = [
  "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now",
  "I need an emergency plumber who can come tonight for a burst pipe",
  "Which DMV office nearby has a same-day appointment open?",
  "Where can I get free groceries today near me?",
];

const PRIORITIES: { value: NonNullable<CreateSwarmRequest["priority"]> | ""; label: string }[] = [
  { value: "", label: "Best overall" },
  { value: "price", label: "Lowest price" },
  { value: "distance", label: "Closest" },
  { value: "speed", label: "Fastest" },
];

export function QueryForm() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [radius, setRadius] = useState(5);
  const [priority, setPriority] = useState("");
  const { caps, error: capsError } = useCapabilities();
  const [mode, setMode] = useState<CallMode>("simulated");
  const modeTouched = useRef(false);
  // Real phone calls are the default as soon as the backend reports live mode is ready
  useEffect(() => {
    if (caps?.live_available && !modeTouched.current) setMode("live");
  }, [caps?.live_available]);
  // A link from the home page can carry a ready-made request (?q=...). It fills the box; it never launches anything.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) setQuery(q.slice(0, 500));
  }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[]>([]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 3 || busy) return;
    setBusy(true);
    setError(null);
    setMissing([]);
    try {
      const body: CreateSwarmRequest = { query: query.trim(), radius_miles: radius, mode };
      if (priority) body.priority = priority as CreateSwarmRequest["priority"];
      if (typeof navigator !== "undefined" && navigator.geolocation && mode === "live") {
        const pos = await new Promise<GeolocationPosition | null>((res) => navigator.geolocation.getCurrentPosition(res, () => res(null), { timeout: 12000, maximumAge: 300000 }));
        if (pos) Object.assign(body, { lat: pos.coords.latitude, lng: pos.coords.longitude });
      }
      const { swarm_id } = await api.createSwarm(body);
      router.push(`/swarm/${swarm_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      if (err instanceof ApiError && err.missing) setMissing(err.missing);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <label htmlFor="q" className="mb-2 block text-sm font-medium">
          What do you need?
        </label>
        <textarea
          id="q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          maxLength={500}
          placeholder="Say it the way you would to a friend."
          className="w-full resize-none rounded-panel border border-line bg-card px-4 py-3 text-[17px] leading-snug placeholder:text-ink-faint focus:border-ink"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
        />
        <ul className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <li key={ex}>
              <button type="button" onClick={() => setQuery(ex)} className="rounded-full border border-line bg-card px-3 py-1.5 text-left text-[13px] text-ink-soft transition-colors hover:border-ink-soft hover:text-ink">
                {ex.length > 52 ? ex.slice(0, 50) + "…" : ex}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_1fr_1.35fr]">
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Search radius</span>
          <select value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="h-11 w-full rounded-md border border-line bg-card px-3">
            {[2, 5, 10, 25].map((r) => (
              <option key={r} value={r}>
                {r} miles
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Pick the winner by</span>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} className="h-11 w-full rounded-md border border-line bg-card px-3">
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <ModePicker mode={mode} onChange={(m) => { modeTouched.current = true; setMode(m); }} caps={caps} />
      </div>

      {capsError && <p className="text-[13px] text-failed">{capsError}</p>}
      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-md border border-failed/40 bg-failed/5 px-3 py-2.5 text-sm text-failed">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div>
            {error}
            {missing.length > 0 && <ul className="mt-1 list-disc pl-5 text-ink-soft">{missing.map((m) => <li key={m}>{m}</li>)}</ul>}
          </div>
        </div>
      )}

      <Button type="submit" disabled={busy || query.trim().length < 3} className="w-full sm:w-auto">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {busy ? "Launching the swarm" : "Launch the swarm"}
        {!busy && <ArrowRight className="h-4 w-4" aria-hidden />}
      </Button>
    </form>
  );
}