"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Headphones, Loader2, Square } from "lucide-react";
import { WS_URL } from "@/lib/api";
import { base64ToBytes, decodeMulaw, parseListenMessage } from "@/lib/audio";
import { cn } from "@/lib/cn";

type Status = "off" | "connecting" | "live" | "ended" | "unavailable";
type Source = "business" | "agent";

const SAMPLE_RATE = 8000; // phone audio; the browser resamples it when it plays
const JITTER_S = 0.12; // small cushion so network hiccups don't make the audio crackle

/**
 * Plays a live call through the browser: the business on the left speaker, the agent on the right.
 * Audio is only streamed while the button is on, and nothing is recorded or saved.
 */
export function ListenButton({ callId, active }: { callId: string; active: boolean }) {
  const [status, setStatus] = useState<Status>("off");
  const [talking, setTalking] = useState<Record<Source, boolean>>({ business: false, agent: false });
  const ctxRef = useRef<AudioContext | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const nextRef = useRef<Record<Source, number>>({ business: 0, agent: 0 });
  const agentNodes = useRef<AudioBufferSourceNode[]>([]);
  const lastHeard = useRef<Record<Source, number>>({ business: 0, agent: 0 });
  const pannerRef = useRef<Record<Source, StereoPannerNode> | null>(null);

  const stop = useCallback((final: Status = "off") => {
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket) {
      socket.onmessage = socket.onclose = socket.onerror = null;
      socket.close();
    }
    for (const node of agentNodes.current) {
      try { node.stop(); } catch {}
    }
    agentNodes.current = [];
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    pannerRef.current = null;
    nextRef.current = { business: 0, agent: 0 };
    setTalking({ business: false, agent: false });
    setStatus(final);
  }, []);

  // Listening belongs to one call: switch calls (or leave the page) and it stops.
  useEffect(() => () => stop("off"), [callId, stop]);
  useEffect(() => {
    if (!active && socketRef.current) stop("ended");
  }, [active, stop]);

  // A little "who is talking" indicator, driven by when audio last arrived from each side.
  useEffect(() => {
    if (status !== "live") return;
    const timer = setInterval(() => {
      const now = performance.now();
      setTalking({ business: now - lastHeard.current.business < 350, agent: now - lastHeard.current.agent < 350 });
    }, 150);
    return () => clearInterval(timer);
  }, [status]);

  function play(src: Source, b64: string) {
    const ctx = ctxRef.current;
    const panner = pannerRef.current?.[src];
    if (!ctx || !panner) return;
    const samples = decodeMulaw(base64ToBytes(b64));
    if (!samples.length) return;
    const buffer = ctx.createBuffer(1, samples.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(samples);
    const node = ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(panner);
    const now = ctx.currentTime;
    const start = Math.max(nextRef.current[src], now + JITTER_S);
    node.start(start);
    nextRef.current[src] = start + buffer.duration;
    lastHeard.current[src] = performance.now();
    if (src === "agent") {
      agentNodes.current.push(node);
      node.onended = () => {
        agentNodes.current = agentNodes.current.filter((n) => n !== node);
      };
    }
  }

  function start() {
    // The click is the user gesture browsers require before they allow sound.
    const Ctx: typeof AudioContext = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    ctx.resume().catch(() => {});
    ctxRef.current = ctx;
    const gain = ctx.createGain();
    gain.gain.value = 1;
    gain.connect(ctx.destination);
    const make = (pan: number) => {
      const p = ctx.createStereoPanner();
      p.pan.value = pan;
      p.connect(gain);
      return p;
    };
    pannerRef.current = { business: make(-0.7), agent: make(0.7) };

    setStatus("connecting");
    const socket = new WebSocket(`${WS_URL}/ws/listen/${callId}`);
    socketRef.current = socket;
    socket.onopen = () => setStatus("live");
    socket.onmessage = (event) => {
      const msg = parseListenMessage(String(event.data));
      if (!msg) return;
      if (msg.t === "audio") play(msg.src, msg.d);
      else if (msg.t === "clear") {
        // The agent was interrupted: drop whatever it had queued but not yet said.
        for (const node of agentNodes.current) {
          try { node.stop(); } catch {}
        }
        agentNodes.current = [];
        nextRef.current.agent = 0;
      } else stop("ended");
    };
    socket.onerror = () => stop("unavailable");
    socket.onclose = (e) => stop(e.code === 4404 ? "unavailable" : "ended");
  }

  const on = status === "connecting" || status === "live";
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => (on ? stop("off") : start())}
        disabled={!active && !on}
        className={cn(
          "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
          on ? "border-talking bg-talking/10 text-talking" : "border-line bg-paper text-ink hover:border-ink-soft",
          !active && !on && "cursor-not-allowed opacity-50",
        )}
        aria-pressed={on}
        title={active || on ? "Hear this call live in your browser" : "Only calls in progress can be listened to"}
      >
        {status === "connecting" ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : on ? <Square className="h-3.5 w-3.5" aria-hidden /> : <Headphones className="h-3.5 w-3.5" aria-hidden />}
        {on ? "Stop listening" : "Listen live"}
      </button>
      {status === "live" && (
        <p className="flex items-center gap-2 text-[11px] text-ink-soft" aria-live="polite">
          <span className={cn("flex items-center gap-1", talking.business && "font-medium text-ink")}>
            <span className={cn("h-1.5 w-1.5 rounded-full", talking.business ? "bg-talking" : "bg-line")} />Business (left)
          </span>
          <span className={cn("flex items-center gap-1", talking.agent && "font-medium text-ink")}>
            <span className={cn("h-1.5 w-1.5 rounded-full", talking.agent ? "bg-talking" : "bg-line")} />Agent (right)
          </span>
        </p>
      )}
      {status === "ended" && <p className="text-[11px] text-ink-soft">Call ended.</p>}
      {status === "unavailable" && <p className="text-[11px] text-ink-soft">No live audio for this call.</p>}
    </div>
  );
}