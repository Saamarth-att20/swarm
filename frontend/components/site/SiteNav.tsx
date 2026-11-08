"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/design/Icon";
import { SdButtonLink } from "@/components/design/SdButton";
import { Logo } from "@/components/site/Logo";
import { useSession } from "@/lib/useSession";

/** Top bar for every page outside a running swarm. Shows Sign in / Get started, or the account once signed in (Auth0). */
export function SiteNav({ current }: { current?: "home" | "app" }) {
  const user = useSession();
  const [open, setOpen] = useState(false);

  return (
    <header className={`header ${current === "app" ? "app-header" : ""}`}>
      <Logo />
      <button
        type="button"
        className="mobile-menu"
        aria-label="Toggle navigation"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Icon name={open ? "close" : "menu"} />
      </button>
      <nav aria-label="Account" className={open ? "open" : ""}>
        {user === undefined ? (
          <span aria-hidden style={{ width: 96, height: 32 }} />
        ) : user ? (
          <>
            {current !== "app" && <SdButtonLink href="/app">Open the app</SdButtonLink>}
            {current === "app" && (
              <Link href="/app" className="nav-link active">
                New search
              </Link>
            )}
            {/* A plain link, not next/link: Auth0 ends the session on its own server and sends the person back */}
            <a href="/auth/logout" className="nav-link">
              Sign out
            </a>
            <span className="avatar" title={user.email} aria-label={user.name}>
              {(user.name.trim()[0] ?? "?").toUpperCase()}
            </span>
          </>
        ) : (
          <>
            <Link href="/signin" className="nav-link">
              Sign in
            </Link>
            <SdButtonLink href="/signup">Get started</SdButtonLink>
          </>
        )}
      </nav>
    </header>
  );
}