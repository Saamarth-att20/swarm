"use client";

import { Logo } from "@/components/site/Logo";
import { ButtonLink, Button } from "@/components/ui/button";
import { useSession } from "@/lib/useSession";

/** Top bar for every page outside a running swarm. Shows Sign in / Get started, or the account once signed in. */
export function SiteNav({ current }: { current?: "home" | "app" }) {
  const user = useSession();

  return (
    <header className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
      <Logo />
      <nav aria-label="Account" className="flex items-center gap-1.5 sm:gap-2">
        {user === undefined ? (
          <span className="h-8 w-24" aria-hidden />
        ) : user ? (
          <>
            <span className="mr-1 hidden text-sm text-ink-soft sm:inline" title={user.email}>{user.name}</span>
            {current !== "app" && <ButtonLink href="/app" size="sm">Open the app</ButtonLink>}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const returnTo = encodeURIComponent(window.location.origin);
                window.location.assign(`/auth/logout?returnTo=${returnTo}`);
              }}
            >
              Sign out
            </Button>
          </>
        ) : (
          <>
            <ButtonLink href="/signin" variant="ghost" size="sm">Sign in</ButtonLink>
            <ButtonLink href="/signup" size="sm">Get started</ButtonLink>
          </>
        )}
      </nav>
    </header>
  );
}