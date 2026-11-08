"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function RecentSwarms() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listSwarms>>>([]);
  useEffect(() => {
    api.listSwarms().then(setItems).catch(() => setItems([]));
  }, []);
  if (items.length === 0) return null;
  return (
    <section aria-label="Recent swarms" className="mt-12">
      <h2 className="font-display text-lg font-semibold">Recent swarms</h2>
      <ul className="mt-3 divide-y divide-line rounded-panel border border-line bg-card">
        {items.map((s) => (
          <li key={s.id}>
            <Link href={`/swarm/${s.id}`} className="flex items-center justify-between gap-4 px-4 py-3 text-sm transition-colors hover:bg-ink/[0.03]">
              <span className="truncate">{s.query}</span>
              <span className="shrink-0 text-xs text-ink-soft">{s.status === "running" ? "Running" : s.status === "completed" ? "Done" : s.status}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
