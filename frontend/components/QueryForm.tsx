"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "@/components/design/Icon";
import { SdButton } from "@/components/design/SdButton";
import { useCapabilities } from "@/lib/useCapabilities";
import { ApiError, api } from "@/lib/api";
import { getMyLocation, type Coords } from "@/lib/geo";
import type { CreateSwarmRequest } from "@/lib/types";

const EXAMPLES = [
  { label: "Prescription in stock", q: "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now" },
  { label: "Emergency plumber tonight", q: "I need an emergency plumber who can come tonight for a burst pipe" },
  { label: "Same-day DMV appointment", q: "Which DMV office nearby has a same-day appointment open?" },
  { label: "Free groceries today", q: "Where can I get free groceries today near me?" },
];

const PRIORITIES: { value: NonNullable<CreateSwarmRequest["priority"]> | ""; label: string }[] = [
  { value: "", label: "Best match" },
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
  // No switch to flip: real phone calls are used whenever the backend says they are ready, otherwise a practice run.
  const mode = caps?.live_available ? "live" : "simulated";
  // A link from the home page can carry a ready-made request (?q=...). It fills the box; it never launches anything.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) setQuery(q.slice(0, 500));
  }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emptyError, setEmptyError] = useState(false);
  const [missing, setMissing] = useState<string[]>([]);
  // Where the user is, once they press "Use my location". Without it, "near me" has nothing to mean.
  const [loc, setLoc] = useState<Coords | null>(null);
  const [locBusy, setLocBusy] = useState(false);
  const [locError, setLocError] = useState<string | null>(null);

  async function useMyLocation() {
    if (locBusy) return;
    setLocBusy(true);
    setLocError(null);
    try {
      setLoc(await getMyLocation());
    } catch (err) {
      setLoc(null);
      setLocError(err instanceof Error ? err.message : "Couldn't get your location.");
    } finally {
      setLocBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (query.trim().length < 3) {
      setEmptyError(true);
      return;
    }
    setBusy(true);
    setError(null);
    setMissing([]);
    try {
      const body: CreateSwarmRequest = { query: query.trim(), radius_miles: radius, mode };
      if (priority) body.priority = priority as CreateSwarmRequest["priority"];
      if (loc) {
        Object.assign(body, { lat: loc.lat, lng: loc.lng });
      } else if (mode === "live") {
        // No button press yet: still try once, so real calls never start without knowing where you are.
        try {
          Object.assign(body, await getMyLocation());
        } catch {
          /* the server explains what to do if it still has no location */
        }
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
    <form onSubmit={submit} className="search-card" noValidate>
      <label className={emptyError ? "has-error" : ""}>
        <span>What should we find?</span>
        <textarea
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setEmptyError(false);
          }}
          maxLength={500}
          placeholder="Example: A pharmacy with children’s amoxicillin in stock tonight"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
        />
        {emptyError && <span className="field-error">Tell us what you need before launching the swarm.</span>}
      </label>
      <div className="mini-chips">
        {EXAMPLES.map((ex) => (
          <button
            type="button"
            key={ex.q}
            onClick={() => {
              setQuery(ex.q);
              setEmptyError(false);
            }}
          >
            {ex.label}
          </button>
        ))}
      </div>

      <div className="search-settings">
        <div>
          <span className="label">Search from</span>
          <button type="button" className={`location-btn ${loc ? "done" : ""}`} onClick={useMyLocation} disabled={locBusy} aria-live="polite">
            {locBusy ? <span className="spinner" /> : <Icon name={loc ? "check" : "pin"} />}
            {locBusy ? "Finding you…" : loc ? "Using your location" : "Use my location"}
          </button>
          {locError ? (
            <span role="alert" className="field-error">
              {locError}
            </span>
          ) : (
            <small>{loc ? "Searches start from where you are right now." : "Or name a place in your request, like “in Austin, TX”."}</small>
          )}
        </div>
        <label>
          <span>Search radius</span>
          <select value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
            {[2, 5, 10, 25].map((r) => (
              <option key={r} value={r}>
                Within {r} miles
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Pick the winner by</span>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {capsError && <p className="field-error form-note">{capsError}</p>}
      {error && (
        <div role="alert" className="form-error">
          <div>
            {error}
            {missing.length > 0 && (
              <ul>
                {missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="launch-row">
        {mode !== "live" && <p className="launch-note">Practice run: made-up businesses, no calls are placed.</p>}
        <SdButton type="submit" variant="dark" icon="arrow" loading={busy}>
          {busy ? "Launching the swarm" : "Launch the swarm"}
        </SdButton>
      </div>
    </form>
  );
}