
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { safeNext } from "@/lib/authRedirect";
import { useSession } from "@/lib/useSession";

export function AuthForm({ mode }: { mode: "signin" | "signup" }) {
  const up = mode === "signup";
  const router = useRouter();
  const user = useSession();

  useEffect(() => {
    if (user) {
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
    }
  }, [user, router]);

  function startAuth() {
    const next = safeNext(
      new URLSearchParams(window.location.search).get("next")
    );

    const params = new URLSearchParams({
      returnTo: next,
    });

    if (up) {
      params.set("screen_hint", "signup");
    }

    window.location.assign(`/auth/login?${params.toString()}`);
  }

  if (user === undefined || user) {
    return (
      <p className="py-4 text-center text-sm text-ink-soft" role="status">
        {user ? "You're already signed in. Redirecting..." : "Checking your account..."}
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-sm leading-relaxed text-ink-soft">
        {up
          ? "Create your Swarm Dial account securely with Auth0."
          : "Sign in securely to access your Swarm Dial account."}
      </p>

      <Button
        type="button"
        size="lg"
        className="w-full"
        onClick={startAuth}
      >
        {up ? "Create account" : "Continue to sign in"}
      </Button>

      <p className="text-xs text-center text-ink-faint">
        Authentication is securely handled by Auth0.
      </p>
    </div>
  );
}
