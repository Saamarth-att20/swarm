"use client";

import { DotRing } from "@/components/design/DotRing";
import { useSession } from "@/lib/useSession";

/** The search page's top: the swarm mark, then a heading addressed to the signed-in person by first name. */
export function AppHeading() {
  const user = useSession();
  const first = user?.name.trim().split(/\s+/)[0];
  // Some accounts only have an email as their name; "Hi name@mail.com" reads badly, so skip the name then.
  const name = first && !first.includes("@") ? first : undefined;
  return (
    <section className="search-hero">
      <span className="greeting-dot">
        <DotRing />
      </span>
      <h1>{name ? `Hi ${name}, what do you need to find?` : "What do you need to find?"}</h1>
      <p>Be specific. We’ll turn your request into one clear question for local businesses.</p>
    </section>
  );
}