"use client";

import { useSession } from "@/lib/useSession";

/** The search page's heading, addressed to the signed-in person by first name. */
export function AppHeading() {
  const user = useSession();
  const first = user?.name.split(/\s+/)[0];
  return (
    <h1 className="text-4xl font-semibold leading-[1.05] sm:text-5xl">
      {first ? `Hi ${first}, what do you need to find?` : "What do you need to find?"}
    </h1>
  );
}