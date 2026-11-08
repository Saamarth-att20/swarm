
"use client";

import { useEffect, useState } from "react";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
}

export function useSession(): AuthUser | null | undefined {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);

  useEffect(() => {
    let active = true;

    async function readSession() {
      try {
        const response = await fetch("/api/auth/session", {
          credentials: "same-origin",
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("Unable to check authentication");
        }

        const data: AuthUser | null = await response.json();

        if (active) {
          setUser(data);
        }
      } catch {
        if (active) {
          setUser(null);
        }
      }
    }

    readSession();

    return () => {
      active = false;
    };
  }, []);

  return user;
}
