/** Helpers for the live "Listen" feature: decode the phone line's 8 kHz mu-law audio into floats the browser can play. */

const MULAW = new Float32Array(256);
for (let i = 0; i < 256; i++) {
  const b = ~i & 0xff;
  const exponent = (b >> 4) & 7;
  const mantissa = b & 0x0f;
  const magnitude = (((mantissa << 3) + 0x84) << exponent) - 0x84;
  MULAW[i] = (b & 0x80 ? -magnitude : magnitude) / 32768;
}

export function decodeMulaw(bytes: Uint8Array): Float32Array {
  const out = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) out[i] = MULAW[bytes[i]];
  return out;
}

export function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export type ListenMessage =
  | { t: "audio"; src: "business" | "agent"; d: string }
  | { t: "clear" }
  | { t: "end" };

export function parseListenMessage(raw: string): ListenMessage | null {
  try {
    const m = JSON.parse(raw);
    if (m?.t === "audio" && (m.src === "business" || m.src === "agent") && typeof m.d === "string") return m;
    if (m?.t === "clear" || m?.t === "end") return m;
  } catch {}
  return null;
}