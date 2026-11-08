import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { CallBoard } from "@/components/site/CallBoard";
import { Footer } from "@/components/site/Footer";
import { SiteNav } from "@/components/site/SiteNav";
import { ButtonLink } from "@/components/ui/button";

export const EXAMPLES = [
  { title: "A pharmacy with the medicine in stock", q: "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now" },
  { title: "A plumber who can come tonight", q: "I need an emergency plumber who can come tonight for a burst pipe" },
  { title: "A DMV with a same-day slot", q: "Which DMV office nearby has a same-day appointment open?" },
  { title: "Free groceries today", q: "Where can I get free groceries today near me?" },
];

const STEPS = [
  { color: "#D98E04", title: "You say what you need", body: "Type it the way you would tell a friend. Name a town or a neighbourhood and we search there instead." },
  { color: "#2557E6", title: "A swarm dials at once", body: "Up to ten callers ring local businesses in parallel. If one doesn't pick up, a backup takes its place." },
  { color: "#7C4DDB", title: "Each caller asks, then listens", body: "They get through phone menus, ask your question in plain words, and write down the price and what's on the shelf." },
  { color: "#17895F", title: "You get one clear answer", body: "A ranked table with a best match on top. Open any call to read exactly what was said." },
];

const LEGEND = [
  ["#D98E04", "Dialing"], ["#2557E6", "Talking"], ["#7C4DDB", "Taking notes"], ["#17895F", "Done"], ["#C93B3B", "Failed"],
];

export function Landing() {
  return (
    <>
      <SiteNav current="home" />
      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-8 sm:px-6 lg:grid-cols-[1fr_1.02fr] lg:gap-16 lg:pb-24 lg:pt-14">
          <div>
            <h1 className="max-w-[13ch] text-[2.75rem] font-semibold leading-[1.02] tracking-tight sm:text-6xl lg:text-[4.25rem]">
              Ten phone calls. One minute.
            </h1>
            <p className="mt-6 max-w-[44ch] text-lg leading-relaxed text-ink-soft">
              Tell Swarm Dial what you&apos;re looking for. AI callers phone the businesses near you at the same time, ask what&apos;s actually in stock right now, and bring back the best answer.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <ButtonLink href="/app" size="lg">
                Try a search <ArrowRight className="h-4 w-4" aria-hidden />
              </ButtonLink>
              <ButtonLink href="/signup" variant="secondary" size="lg">Create an account</ButtonLink>
            </div>
            <p className="mt-4 text-sm text-ink-faint">Free to try. You&apos;ll sign in before your first search.</p>
          </div>
          <div>
            <CallBoard />
            <p className="mt-3 text-center text-[13px] text-ink-faint">A sample run with made-up businesses.</p>
          </div>
        </section>

        <section className="border-y border-line bg-card">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
            <h2 className="max-w-[22ch] text-3xl font-semibold leading-tight sm:text-4xl">The calls you were going to make yourself</h2>
            <p className="mt-3 max-w-[52ch] text-ink-soft">Pick one to start, or write your own. Nothing is dialed until you launch it.</p>
            <ul className="mt-8 grid gap-3 sm:grid-cols-2">
              {EXAMPLES.map((ex) => (
                <li key={ex.q}>
                  <Link
                    href={`/app?q=${encodeURIComponent(ex.q)}`}
                    className="group flex h-full items-start justify-between gap-4 rounded-panel border border-line bg-paper p-5 transition-colors hover:border-ink"
                  >
                    <span>
                      <span className="block font-display text-lg font-semibold">{ex.title}</span>
                      <span className="mt-1 block text-[14px] leading-snug text-ink-soft">“{ex.q}”</span>
                    </span>
                    <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
          <h2 className="max-w-[20ch] text-3xl font-semibold leading-tight sm:text-4xl">How a search works</h2>
          <ol className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="border-t-2 pt-4" style={{ borderColor: s.color }}>
                <p className="text-sm font-medium text-ink-faint">Step {i + 1}</p>
                <h3 className="mt-1 font-display text-xl font-semibold leading-snug">{s.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">{s.body}</p>
              </li>
            ))}
          </ol>
          <ul className="mt-10 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-soft" aria-label="What the colours mean">
            {LEGEND.map(([c, l]) => (
              <li key={l} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} aria-hidden /> {l}
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-ink text-paper">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:py-20">
            <h2 className="max-w-[16ch] text-3xl font-semibold leading-tight sm:text-4xl">Honest about being a robot</h2>
            <ul className="space-y-5 text-[16px] leading-relaxed text-paper/80">
              <li><strong className="font-semibold text-paper">Every call says it&apos;s an AI.</strong> The caller tells the business who it is and why it&apos;s calling, and ends politely if they&apos;d rather not talk.</li>
              <li><strong className="font-semibold text-paper">Short, polite, and to the point.</strong> It asks your question, thanks them, and hangs up. It never pretends to be you.</li>
              <li><strong className="font-semibold text-paper">You can read every word.</strong> Each call&apos;s transcript sits next to its result, so you can check the answer yourself.</li>
            </ul>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6 lg:py-24">
          <h2 className="mx-auto max-w-[18ch] text-3xl font-semibold leading-tight sm:text-5xl">Stop being on hold. Start with one question.</h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/app" size="lg">Try a search <ArrowRight className="h-4 w-4" aria-hidden /></ButtonLink>
            <ButtonLink href="/signin" variant="secondary" size="lg">Sign in</ButtonLink>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}