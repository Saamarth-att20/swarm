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

export function CommanderLog({ swarm }: { swarm: SwarmView }) {
  const items = [...swarm.log].reverse();
  return (
    <section className="rounded-panel border border-line bg-card" aria-label="Commander activity">
      <header className="border-b border-line px-4 py-3">
        <h2 className="font-display text-lg font-semibold">Commander</h2>
        <p className="text-xs text-ink-soft">Reroutes and what the agents have learned so far.</p>
      </header>
      <ul className="scroll-quiet max-h-[300px] divide-y divide-line overflow-y-auto" aria-live="polite">
        {items.length === 0 && <li className="px-4 py-6 text-center text-sm text-ink-faint">Nothing to coordinate yet.</li>}
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.li key={item.seq} initial={{ opacity: 0, backgroundColor: "#F2C94C33" }} animate={{ opacity: 1, backgroundColor: "#F2C94C00" }} transition={{ duration: 1.2 }} className="flex gap-2.5 px-4 py-2.5 text-[13px] leading-snug">
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
