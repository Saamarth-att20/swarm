/**
 * The one place the pages talk to "accounts".
 *
 * This is a DEMO adapter: it keeps a session in this browser only and does not check passwords, so anyone can "sign in".
 * It exists so the sign in / sign up pages and the signed-in header can be built and tested now. The real authentication
 * (Jaswant's) replaces the bodies of signUp / signIn / signOut / getSession and flips AUTH_IS_DEMO to false; the pages
 * and components do not change.
 *
 * Author: Saamarth Attray
 */

export interface AuthUser {
  id: string;
  name: string;
  email: string;
}

export class AuthError extends Error {
  constructor(message: string, readonly field?: "name" | "email" | "password") {
    super(message);
    this.name = "AuthError";
  }
}

export const AUTH_IS_DEMO = true;

const KEY = "swarmdial.session";
const EVENT = "swarmdial:session";

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStore(): Store | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null; // private mode / blocked storage: behave as signed out
  }
}

function announce() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
}

function userFor(email: string, name?: string): AuthUser {
  const clean = email.trim().toLowerCase();
  const local = clean.split("@")[0] || "there";
  const pretty = local.replace(/[._-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return { id: `u_${clean}`, name: (name ?? pretty).trim(), email: clean };
}

export function getSession(store: Store | null = browserStore()): AuthUser | null {
  try {
    const raw = store?.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<AuthUser>;
    return data.id && data.email && data.name ? (data as AuthUser) : null;
  } catch {
    return null;
  }
}

function save(user: AuthUser, store: Store | null) {
  try {
    store?.setItem(KEY, JSON.stringify(user));
  } catch {
    throw new AuthError("Your browser is blocking storage, so we can't keep you signed in. Allow site data and try again.");
  }
  announce();
}

export async function signUp(input: { name: string; email: string; password: string }, store: Store | null = browserStore()): Promise<AuthUser> {
  const user = userFor(input.email, input.name);
  save(user, store);
  return user;
}

export async function signIn(input: { email: string; password: string }, store: Store | null = browserStore()): Promise<AuthUser> {
  const user = userFor(input.email);
  save(user, store);
  return user;
}

export async function signOut(store: Store | null = browserStore()): Promise<void> {
  try {
    store?.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
  announce();
}

/** Calls `listener` whenever the session changes in this tab or another one. Returns an unsubscribe function. */
export function onSessionChange(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY || e.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener("storage", onStorage);
  };
}