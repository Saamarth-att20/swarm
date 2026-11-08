/** Where to send someone after they sign in. Only same-site paths are allowed, so a crafted link can't bounce them elsewhere. Author: Saamarth Attray */

export const DEFAULT_AFTER_SIGN_IN = "/app";

export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return DEFAULT_AFTER_SIGN_IN;
  if (value.startsWith("/signin") || value.startsWith("/signup")) return DEFAULT_AFTER_SIGN_IN;
  return value;
}

/** The sign-in address that brings the person back to `path` afterwards. */
export function signInUrl(path: string): string {
  return `/signin?next=${encodeURIComponent(safeNext(path))}`;
}