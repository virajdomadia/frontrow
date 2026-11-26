"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, safeNext, send } from "@/lib/client";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DemoButtons } from "./DemoButtons";

type Mode = "sign-in" | "sign-up";

/**
 * S9: email + password, with a role picker on sign-up. Used on the auth pages and inline at
 * checkout (`onDone` instead of a redirect), so a visitor never loses their held seats.
 */
export function AuthForm({
  mode: initial,
  next,
  onDone,
  compact = false,
}: {
  mode: Mode;
  next?: string;
  /** Inline use: called with the user instead of navigating. */
  onDone?: (me: Me) => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const id = useId();
  const [mode, setMode] = useState<Mode>(initial);
  const [role, setRole] = useState<"customer" | "organiser">("customer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  function finish(me: Me) {
    if (onDone) return onDone(me);
    const fallback = me.role === "organiser" ? "/organiser" : "/events";
    router.replace(safeNext(next, fallback));
    router.refresh();
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setFields({});
    try {
      const body =
        mode === "sign-in"
          ? { email: data.get("email"), password: data.get("password") }
          : { email: data.get("email"), password: data.get("password"), name: data.get("name"), role };
      finish(await send<Me>("POST", `/auth/${mode}`, body));
    } catch (err) {
      setError(messageOf(err));
      setFields(fieldErrors(err));
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-btn border border-ink/25 bg-white/70 px-3 py-2.5 text-[16px] text-ink placeholder:text-ink-3 focus-visible:border-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber aria-invalid:border-red-dark";
  const label = "grid gap-1.5 text-sm font-semibold text-ink-2";

  return (
    <div className="grid gap-5">
      <form onSubmit={submit} noValidate={false} className="grid gap-4" aria-describedby={error ? `${id}-err` : undefined}>
        {mode === "sign-up" && (
          <>
            <fieldset className="grid gap-2 border-0 p-0">
              <legend className="mb-1.5 text-sm font-semibold text-ink-2">I&apos;m here to</legend>
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    ["customer", "Book seats", "Movies and concerts"],
                    ["organiser", "Sell tickets", "Venues, shows, bookings"],
                  ] as const
                ).map(([value, title, sub]) => (
                  <label
                    key={value}
                    className={cn(
                      "cursor-pointer rounded-card border-2 px-3 py-2.5 transition-colors has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                      role === value ? "border-ink bg-white/60" : "border-ink/15 hover:border-ink/40",
                    )}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={value}
                      checked={role === value}
                      onChange={() => setRole(value)}
                      className="sr-only"
                    />
                    <b className="block font-cond text-xl font-bold uppercase">{title}</b>
                    <span className="text-xs text-ink-2">{sub}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label className={label}>
              {role === "organiser" ? "Organisation name" : "Your name"}
              <input
                name="name"
                required
                maxLength={80}
                autoComplete={role === "organiser" ? "organization" : "name"}
                className={input}
                aria-invalid={!!fields.name}
              />
            </label>
          </>
        )}
        <label className={label}>
          Email
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            className={input}
            aria-invalid={!!fields.email}
          />
        </label>
        <label className={label}>
          Password
          <input
            name="password"
            type="password"
            required
            minLength={mode === "sign-up" ? 8 : 1}
            autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
            className={input}
            aria-invalid={!!fields.password}
            aria-describedby={mode === "sign-up" ? `${id}-pw` : undefined}
          />
          {mode === "sign-up" && (
            <span id={`${id}-pw`} className="text-xs font-normal text-ink-3">
              At least 8 characters
            </span>
          )}
        </label>
        {mode === "sign-in" && (
          <p className="-mt-2 text-xs text-ink-3">
            Forgot your password? Password reset by email arrives with ticket emails — for now, write to
            hello@frontrow.demo.
          </p>
        )}
        {error && (
          <p id={`${id}-err`} role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "One moment…" : mode === "sign-in" ? "Sign in" : role === "organiser" ? "Create organiser account" : "Create account"}
        </Button>
        <p className="text-center text-sm text-ink-2">
          {mode === "sign-in" ? "New to Frontrow? " : "Already have an account? "}
          {onDone ? (
            <button
              type="button"
              onClick={() => {
                setMode(mode === "sign-in" ? "sign-up" : "sign-in");
                setError("");
                setFields({});
              }}
              className="cursor-pointer font-semibold text-ink underline underline-offset-4"
            >
              {mode === "sign-in" ? "Create an account" : "Sign in"}
            </button>
          ) : (
            <Link
              href={`/${mode === "sign-in" ? "sign-up" : "sign-in"}${next ? `?next=${encodeURIComponent(next)}` : ""}`}
              className="font-semibold text-ink underline underline-offset-4"
            >
              {mode === "sign-in" ? "Create an account" : "Sign in"}
            </Link>
          )}
        </p>
      </form>

      <div className={cn("grid gap-2.5 border-t border-dashed border-ink/25 pt-4", compact && "pt-3")}>
        <p className="text-center text-xs font-semibold tracking-[.12em] text-ink-2 uppercase">Or try a demo account</p>
        <DemoButtons next={next} onDone={onDone} only={onDone ? "customer" : undefined} tone="paper" />
      </div>
    </div>
  );
}
