import { Logo } from "@/components/site/Logo";

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-ink-soft sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <Logo className="[&_span]:text-base" />
        <p>Built for a hackathon by Saamarth Attray and Jaswant. Calls always say they are from an AI assistant.</p>
      </div>
    </footer>
  );
}