"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { signInUrl } from "@/lib/authRedirect";
import { useSession } from "@/lib/useSession";

/** Wrap a page that needs an account. Signed-out visitors go to sign in and come back to the same page afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const user = useSession();
  const router = useRouter();

  useEffect(() => {
    if (user === null) router.replace(signInUrl(window.location.pathname + window.location.search));
  }, [user, router]);

  if (!user) {
    // undefined = still checking the browser, null = about to redirect. Show nothing that could flash private content.
    return <p className="py-24 text-center text-sm text-ink-faint" role="status">Checking your account…</p>;
  }
  return <>{children}</>;
}