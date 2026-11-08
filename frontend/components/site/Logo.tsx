import Link from "next/link";
import { DotRing } from "@/components/design/DotRing";
import { cn } from "@/lib/cn";

/** The ring of callers around the dial. Kept under its old name so existing imports keep working. */
export function LogoMark() {
  return <DotRing />;
}

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <Link href="/" aria-label="Swarm Dial home" className={cn("logo", className)}>
      <DotRing />
      {!compact && <span>Swarm Dial</span>}
    </Link>
  );
}