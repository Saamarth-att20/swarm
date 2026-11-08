"use client";

import { useEffect, useState } from "react";
import { getSession, onSessionChange, type AuthUser } from "@/lib/auth";

/** undefined while we check the browser (so the header doesn't flash "Sign in" for a signed-in person), then user or null. */
export function useSession(): AuthUser | null | undefined {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  useEffect(() => {
    const read = () => setUser(getSession());
    read();
    return onSessionChange(read);
  }, []);
  return user;
}