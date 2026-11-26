"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { fieldErrors, messageOf, safeNext, send } from "@/lib/client";
import type { Door, Me } from "@/lib/types";
import { cn } from "@/lib/utils";

type Step = "email" | "code" | "details";

const HOME: Record<Door, string> = {
  customer: "/",
  business: "/owner",
  staff: "/staff/businesses?status=pending",
};

export const inputClass =
  "w-full rounded-btn border border-ink/25 bg-white/80 px-3 py-2.5 text-[16px] text-ink placeholder:text-ink-3 focus-visible:border-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber aria-invalid:border-red-dark";
export const labelClass = "grid gap-1.5 text-sm font-semibold text-ink-2";

/**
 * Sign-in by email code (R1), for all three doors: email → 6-digit code → (a new customer's
 * name | a new business's details) → signed in. No passwords. Used on /sign-in, /business/*,
 * /staff, and inline at Proceed (`onDone` instead of a redirect) so held seats are never lost.
 */
export function CodeSignIn({
  door = "customer",
  next,
  onDone,
  submitLabel,
}: {
  door?: Door;
  next?: string;
  onDone?: (me: Me) => void;
  submitLabel?: string;
}) {
  const router = useRouter();
  const id = useId();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [resendIn, setResendIn] = useState(0);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (resendIn <= 0) return;
    const t = window.setTimeout(() => setResendIn((n) => n - 1), 1000);
    return () => window.clearTimeout(t);
  }, [resendIn]);

  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
  }, [step]);

  function finish(me: Me) {
    if (onDone) return onDone(me);
    router.replace(safeNext(next, HOME[door]));
    router.refresh();
  }

  function fail(e: unknown) {
    setError(messageOf(e));
    setFields(fieldErrors(e));
    setBusy(false);
  }

  async function sendCode(to = email) {
    setBusy(true);
    setError("");
    setFields({});
    try {
      await send("POST", "/auth/code", { email: to, door });
      setEmail(to.trim().toLowerCase());
      setStep("code");
      setResendIn(60);
      setBusy(false);
    } catch (e) {
      if (e instanceof ApiRequestError && e.body.code === "rate_limited" && step === "code") {
        setResendIn(Number((e.body.details as { retry_after?: number } | undefined)?.retry_after ?? 60));
      }
      fail(e);
    }
  }

  async function verify(extra: Record<string, unknown> = {}) {
    setBusy(true);
    setError("");
    setFields({});
    try {
      finish(await send<Me>("POST", "/auth/verify", { email, code, door, ...extra }));
    } catch (e) {
      if (e instanceof ApiRequestError && (e.body.code === "name_required" || e.body.code === "business_required")) {
        setMissing(((e.body.details as { missing?: string[] } | undefined)?.missing ?? ["name"]) as string[]);
        setStep("details");
        setBusy(false);
        return;
      }
      fail(e);
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    if (step === "email") return void sendCode(String(data.get("email") ?? ""));
    if (step === "code") return void verify();
    const extra: Record<string, unknown> = {};
    if (missing.includes("name")) extra.name = String(data.get("name") ?? "");
    if (missing.includes("business"))
      extra.business = { name: String(data.get("business_name") ?? ""), phone: String(data.get("phone") ?? "") };
    void verify(extra);
  }

  const errId = `${id}-err`;
  return (
    <form onSubmit={onSubmit} className="grid gap-4" aria-describedby={error ? errId : undefined}>
      {step === "email" && (
        <label className={labelClass}>
          Email
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            defaultValue={email}
            className={inputClass}
            aria-invalid={!!fields.email}
            placeholder="you@example.com"
          />
          <span className="text-xs font-normal text-ink-3">We&apos;ll email you a 6-digit code. No password needed.</span>
        </label>
      )}

      {step === "code" && (
        <>
          <p className="text-sm text-ink-2">
            We sent a code to <b className="text-ink">{email}</b>. It works for 10 minutes.
          </p>
          <label className={labelClass}>
            6-digit code
            <input
              ref={codeRef}
              name="code"
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              className={cn(inputClass, "font-mono text-2xl tracking-[.4em]")}
              aria-invalid={!!error}
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setCode("");
                setError("");
              }}
              className="cursor-pointer font-semibold text-ink underline underline-offset-4"
            >
              Use a different email
            </button>
            <button
              type="button"
              disabled={resendIn > 0 || busy}
              onClick={() => void sendCode()}
              className="cursor-pointer font-semibold text-ink underline underline-offset-4 disabled:cursor-default disabled:text-ink-3 disabled:no-underline"
            >
              {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
            </button>
          </div>
        </>
      )}

      {step === "details" && (
        <>
          <p className="text-sm text-ink-2">
            {missing.includes("business") ? "One more step: tell us about your cinema business." : "Welcome! What should we call you?"}
          </p>
          {missing.includes("name") && (
            <label className={labelClass}>
              Your name
              <input name="name" required maxLength={80} autoComplete="name" className={inputClass} aria-invalid={!!fields.name} />
            </label>
          )}
          {missing.includes("business") && (
            <>
              <label className={labelClass}>
                Business name
                <input
                  name="business_name"
                  required
                  minLength={2}
                  maxLength={80}
                  autoComplete="organization"
                  placeholder="e.g. Sunrise Talkies"
                  className={inputClass}
                  aria-invalid={!!fields["business.name"]}
                />
              </label>
              <label className={labelClass}>
                Phone
                <input
                  name="phone"
                  required
                  type="tel"
                  autoComplete="tel"
                  placeholder="+91 80 1234 5678"
                  className={inputClass}
                  aria-invalid={!!fields["business.phone"]}
                />
                <span className="text-xs font-normal text-ink-3">Frontrow staff call this number once to verify you.</span>
              </label>
            </>
          )}
        </>
      )}

      {error && (
        <p id={errId} role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
          {error}
        </p>
      )}
      <Button type="submit" disabled={busy || (step === "code" && code.length !== 6)} className="w-full">
        {busy
          ? "One moment…"
          : step === "email"
            ? "Email me a code"
            : step === "code"
              ? (submitLabel ?? "Sign in")
              : missing.includes("business")
                ? "Register business"
                : "Continue"}
      </Button>
    </form>
  );
}
