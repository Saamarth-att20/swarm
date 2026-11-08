"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { Eye, EyeOff, Loader2, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AUTH_IS_DEMO, AuthError, signIn, signUp } from "@/lib/auth";
import { safeNext } from "@/lib/authRedirect";
import { passwordStrength, validateSignIn, validateSignUp, type FieldErrors } from "@/lib/authValidation";
import { useSession } from "@/lib/useSession";

const BAR = ["#C93B3B", "#C93B3B", "#D98E04", "#17895F", "#17895F"];

function Field({ label, error, children, id }: { label: string; error?: string; children: React.ReactNode; id: string }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      {children}
      {error && <p id={`${id}-err`} className="mt-1.5 text-[13px] text-failed">{error}</p>}
    </div>
  );
}

const inputClass = (bad?: boolean) =>
  `h-11 w-full rounded-md border bg-card px-3 text-[16px] placeholder:text-ink-faint focus:border-ink ${bad ? "border-failed" : "border-line"}`;

export function AuthForm({ mode }: { mode: "signin" | "signup" }) {
  const up = mode === "signup";
  const router = useRouter();
  const uid = useId();
  const user = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Where to go afterwards: the page that sent them here (?next=...), or the app.
  const nextPath = () => safeNext(new URLSearchParams(window.location.search).get("next"));

  useEffect(() => {
    if (user) router.replace(safeNext(new URLSearchParams(window.location.search).get("next"))); // already signed in
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const found = up ? validateSignUp({ name, email, password }) : validateSignIn({ email, password });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      if (up) await signUp({ name: name.trim(), email: email.trim(), password });
      else await signIn({ email: email.trim(), password });
      router.push(nextPath());
    } catch (err) {
      if (err instanceof AuthError && err.field) setErrors({ [err.field]: err.message });
      else setFormError(err instanceof Error ? err.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  const strength = up ? passwordStrength(password) : null;
  const id = (k: string) => `${uid}-${k}`;

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {up && (
        <Field id={id("name")} label="Your name" error={errors.name}>
          <input id={id("name")} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!!errors.name} aria-describedby={errors.name ? `${id("name")}-err` : undefined} className={inputClass(!!errors.name)} />
        </Field>
      )}
      <Field id={id("email")} label="Email" error={errors.email}>
        <input id={id("email")} type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={!!errors.email} aria-describedby={errors.email ? `${id("email")}-err` : undefined} className={inputClass(!!errors.email)} />
      </Field>
      <Field id={id("password")} label="Password" error={errors.password}>
        <div className="relative">
          <input
            id={id("password")}
            type={show ? "text" : "password"}
            autoComplete={up ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!errors.password}
            aria-describedby={errors.password ? `${id("password")}-err` : undefined}
            className={inputClass(!!errors.password) + " pr-11"}
          />
          <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-ink-faint hover:text-ink">
            {show ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
          </button>
        </div>
        {strength && password && (
          <div className="mt-2" aria-live="polite">
            <div className="flex gap-1" aria-hidden>
              {[1, 2, 3, 4].map((n) => (
                <span key={n} className="h-1 flex-1 rounded-full bg-line" style={n <= strength.score ? { background: BAR[strength.score] } : undefined} />
              ))}
            </div>
            <p className="mt-1.5 text-[13px] text-ink-soft">{strength.hint}</p>
          </div>
        )}
      </Field>

      {formError && (
        <div role="alert" className="flex items-start gap-2 rounded-md border border-failed/40 bg-failed/5 px-3 py-2.5 text-sm text-failed">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {formError}
        </div>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {up ? (busy ? "Creating your account" : "Create account") : busy ? "Signing in" : "Sign in"}
      </Button>

      {AUTH_IS_DEMO && (
        <p className="rounded-md bg-ink/[0.05] px-3 py-2.5 text-[13px] leading-snug text-ink-soft">
          Demo mode: accounts are kept in this browser only, and passwords aren&apos;t checked yet.
        </p>
      )}

      <p className="text-sm text-ink-soft">
        {up ? "Already have an account? " : "New here? "}
        <Link href={up ? "/signin" : "/signup"} className="font-medium text-ink underline underline-offset-4">
          {up ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </form>
  );
}