"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { ApiError, WS_URL, api } from "./api";
import { applyEvent, initialSwarm } from "./reducer";
import type { SwarmEvent, SwarmView } from "./types";

export type Connection = "connecting" | "live" | "reconnecting" | "closed" | "not_found" | "unreachable";

type Action = { type: "event"; event: SwarmEvent } | { type: "reset"; id: string } | { type: "reserving"; callId: string | null };

function reduce(state: SwarmView, action: Action): SwarmView {
  if (action.type === "reset") return initialSwarm(action.id);
  if (action.type === "reserving") return { ...state, reserving: action.callId };
  return applyEvent(state, action.event);
}

/**
 * Streams one swarm. The server replays everything after `?after=<seq>` and then goes live, so the same
 * code path handles first load, tab refresh and a dropped connection.
 */
export function useSwarm(swarmId: string) {
  const [state, dispatch] = useReducer(reduce, swarmId, initialSwarm);
  const [connection, setConnection] = useState<Connection>("connecting");
  const lastSeq = useRef(0);
  lastSeq.current = state.lastSeq;
  const finished = useRef(false);
  finished.current = Boolean(state.completed);

  useEffect(() => {
    dispatch({ type: "reset", id: swarmId });
    lastSeq.current = 0;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let disposed = false;

    const open = () => {
      if (disposed) return;
      let everOpened = false;
      socket = new WebSocket(`${WS_URL}/ws/swarms/${swarmId}?after=${lastSeq.current}`);
      socket.onopen = () => {
        everOpened = true;
        attempts = 0;
        setConnection("live");
      };
      socket.onmessage = (m) => {
        try {
          dispatch({ type: "event", event: JSON.parse(m.data) as SwarmEvent });
        } catch {
          /* ignore malformed frame */
        }
      };
      socket.onclose = async () => {
        if (disposed) return;
        if (finished.current) return setConnection("closed");
        attempts += 1;
        if (!everOpened && attempts >= 2) {
          try {
            await api.getSwarm(swarmId);
          } catch (e) {
            if (e instanceof ApiError) return setConnection(e.status === 404 ? "not_found" : "unreachable");
          }
        }
        setConnection("reconnecting");
        timer = setTimeout(open, Math.min(500 * 2 ** attempts, 8000));
      };
    };
    open();

    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [swarmId]);

  return { state, connection, markReserving: (callId: string | null) => dispatch({ type: "reserving", callId }) };
}
