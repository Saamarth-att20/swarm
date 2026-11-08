import Link from "next/link";
import { cn } from "@/lib/cn";

const DOTS = Array.from({ length: 8 }, (_, i) => {
  const a = (i * Math.PI) / 4 - Math.PI / 2;
  return { x: +(16 + 11 * Math.cos(a)).toFixed(2), y: +(16 + 11 * Math.sin(a)).toFixed(2) };
});

/** A ring of callers around one dial: the swarm, dialing. One caller is amber because it is ringing. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-7 w-7", className)} aria-hidden>
      {DOTS.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r={2.3} fill={i === 1 ? "#D98E04" : "currentColor"} opacity={i === 1 ? 1 : 0.9} />
      ))}
      <circle cx={16} cy={16} r={3.6} fill="currentColor" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" aria-label="Swarm Dial home" className={cn("flex items-center gap-2.5 text-ink", className)}>
      <LogoMark />
      <span className="font-display text-xl font-semibold tracking-tight">Swarm Dial</span>
    </Link>
  );
}