import type { ReactNode } from "react";
import { CallBoard } from "@/components/site/CallBoard";
import { Logo } from "@/components/site/Logo";

/** Two columns: the form on the left, the sample run on the right (hidden on small screens). */
export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <main className="flex flex-col px-4 py-6 sm:px-10">
        <Logo />
        <div className="mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-10">
          <h1 className="text-4xl font-semibold leading-tight">{title}</h1>
          <p className="mt-2 text-ink-soft">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
      <aside className="hidden items-center justify-center bg-card px-10 lg:flex" aria-hidden>
        <div className="w-full max-w-lg">
          <CallBoard />
          <p className="mt-4 text-center text-[13px] text-ink-faint">A sample run with made-up businesses.</p>
        </div>
      </aside>
    </div>
  );
}