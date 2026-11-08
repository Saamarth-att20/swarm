"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Brain, CornerUpRight } from "lucide-react";
import { cn } from "@/lib/cn";
import type { SwarmView } from "@/lib/types";

const TONE: Record<string, string> = {
  closed: "text-dialing",
  no_stock: "text-failed",
  failed: "text-failed",
  referral: "text-extracting",
  backup: "text-talking",
};

/** What the Commander decided (reroutes) and what the callers learned along the way, newest first. */
export function CommanderLog({ swarm }: { swarm: SwarmView }) {
  const items = [...swarm.log].reverse();
  return (
    <section className="panel" aria-label="Commander activity">
      <div className="section-row">
        <h2>Commander</h2>
      </div>
      <p className="panel-note">Reroutes and what the agents have learned so far.</p>
      <ul className="log-list scroll-quiet" aria-live="polite">
        {items.length === 0 && <li className="log-empty">Nothing to coordinate yet.</li>}
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.li key={item.seq} initial={{ opacity: 0, backgroundColor: "#F2C94C33" }} animate={{ opacity: 1, backgroundColor: "#F2C94C00" }} transition={{ duration: 1.2 }}>
              {item.kind === "reroute" ? (
                <CornerUpRight className={cn("mt-0.5 h-4 w-4 shrink-0", TONE[item.tone])} aria-label="Rerouted" />
              ) : (
                <Brain className="mt-0.5 h-4 w-4 shrink-0 text-extracting" aria-label="Learned" />
              )}
              <span>{item.message}</span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </section>
  );
}