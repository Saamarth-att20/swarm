import Link from "next/link";
import { Constellation } from "@/components/design/Constellation";
import { DotRing } from "@/components/design/DotRing";
import { Icon, type IconName } from "@/components/design/Icon";
import { SampleBoard } from "@/components/design/SampleBoard";
import { SdButtonLink } from "@/components/design/SdButton";
import { Wave } from "@/components/design/Wave";
import { Footer } from "@/components/site/Footer";
import { SiteNav } from "@/components/site/SiteNav";

export const EXAMPLES: { title: string; q: string; icon: IconName }[] = [
  { title: "A pharmacy with the medicine in stock", q: "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now", icon: "phone" },
  { title: "A plumber who can come tonight", q: "I need an emergency plumber who can come tonight for a burst pipe", icon: "clock" },
  { title: "A DMV with a same-day slot", q: "Which DMV office nearby has a same-day appointment open?", icon: "pin" },
  { title: "Free groceries today", q: "Where can I get free groceries today near me?", icon: "clock" },
];

export function Landing() {
  return (
    <div className="page landing route-view">
      <div className="hero-band">
        <SiteNav current="home" />
        <section className="hero sd-container">
          <div className="hero-copy">
            <h1>
              <span>Ten phone calls.</span>
              <span>One minute.</span>
            </h1>
            <p>
              AI callers phone local businesses at the same time, ask what’s available right now, and bring back the best answer.
            </p>
            <div className="button-row">
              <SdButtonLink href="/app" icon="arrow">
                Try a search
              </SdButtonLink>
              <SdButtonLink href="/signup" variant="secondary">
                Create an account
              </SdButtonLink>
            </div>
          </div>
          <div className="hero-board">
            <SampleBoard />
          </div>
        </section>
      </div>
      <main>
        <section className="how sd-container">
          <div className="section-heading centered">
            <h2>How it works</h2>
          </div>
          <div className="steps">
            <article>
              <span className="step-icon">
                <Icon name="spark" />
              </span>
              <h3>You ask in plain language</h3>
              <p>Describe the thing you need, how far you can travel, and what matters most.</p>
            </article>
            <article>
              <span className="step-icon">
                <Wave />
              </span>
              <h3>Callers phone in parallel</h3>
              <p>Up to ten AI callers identify themselves, ask your question, and compare answers live.</p>
            </article>
            <article>
              <span className="step-icon green">
                <Icon name="check" />
              </span>
              <h3>You get the best answer</h3>
              <p>See who has it, what they said, and read every word of the call.</p>
            </article>
          </div>
        </section>

        <section className="honest-section">
          <div className="sd-container honest-grid">
            <div>
              <span className="robot-orbit">
                <DotRing />
              </span>
            </div>
            <div>
              <h2>Honest about being a robot</h2>
              <p>
                Every call starts the same way: “Hi, I’m an AI assistant calling on behalf of a person nearby.” No pretending. No tricks. Businesses can decline, and we’ll thank them and move on.
              </p>
            </div>
          </div>
        </section>

        <section className="examples sd-container">
          <div className="section-heading centered">
            <h2>For the things that can’t wait</h2>
          </div>
          <div className="chip-grid">
            {EXAMPLES.map((ex) => (
              <Link key={ex.q} href={`/app?q=${encodeURIComponent(ex.q)}`} className="example-chip">
                <Icon name={ex.icon} />
                <span>{ex.title}</span>
                <Icon name="arrow" />
              </Link>
            ))}
          </div>
        </section>

        <section className="cta-band">
          <div className="sd-container cta-band-inner">
            <div className="cta-copy">
              <h2>Stop calling one by one.</h2>
              <p>Send the swarm and get back to what matters.</p>
              <SdButtonLink href="/app" variant="dark" icon="arrow">
                Try your first search
              </SdButtonLink>
            </div>
            <div className="cta-panel">
              <Constellation />
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}