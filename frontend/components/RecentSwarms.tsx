"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/design/Icon";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/timeAgo";

const STATUS_LABEL: Record<string, string> = { running: "Running", completed: "Done" };

export function RecentSwarms() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listSwarms>>>([]);
  useEffect(() => {
    api.listSwarms().then(setItems).catch(() => setItems([]));
  }, []);
  if (items.length === 0) return null;
  return (
    <section aria-label="Recent searches" className="recent">
      <div className="recent-head">
        <h2>Recent searches</h2>
      </div>
      <div className="recent-list">
        {items.map((s) => (
          <Link key={s.id} href={`/swarm/${s.id}`} className="recent-row">
            <article>
              <span className={`recent-icon ${s.status === "completed" ? "found" : ""}`}>
                <Icon name={s.status === "completed" ? "check" : "clock"} />
              </span>
              <div>
                <strong>{s.query}</strong>
                <span>
                  {s.mode === "live" ? "Real phones" : "Practice run"} · {timeAgo(s.created_at)}
                </span>
              </div>
              <span className="result-count">{STATUS_LABEL[s.status] ?? s.status}</span>
              <Icon name="arrow" size={18} />
            </article>
          </Link>
        ))}
      </div>
    </section>
  );
}