"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Capabilities } from "./types";

export function useCapabilities() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.capabilities().then(setCaps).catch((e: Error) => setError(e.message));
  }, []);
  return { caps, error };
}
