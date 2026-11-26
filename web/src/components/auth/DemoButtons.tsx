"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { messageOf, safeNext, send } from "@/lib/client";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";

type Role = "customer" | "organiser";

const COPY: Record<Role, { label: string; sub: string }> = {
  customer: { label: "Demo customer", sub: "Book seats, see tickets" },
  organiser: { label: "Demo organiser", sub: "Venues, shows, bookings" },
};

/**
 * One-click sign-in as a seeded demo account (F4: "demo customer signs in from landing in one
 * click"). On the landing page, the auth pages, and inline at checkout (customer only).
 */
export function DemoButtons({
  next,
  onDone,
  only,
  tone = "plum",
  className,
}: {
  next?: string;
  onDone?: (me: Me) => void;
  only?: Role;
  tone?: "plum" | "paper";
  className?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState("");

  async function go(as: Role) {
    setBusy(as);
    setError("");
    try {
      const me = await send<Me>("POST", "/auth/demo", { as });
      if (onDone) return onDone(me);
      router.push(safeNext(next, as === "organiser" ? "/organiser" : "/events"));
      router.refresh();
    } catch (e) {
      setError(messageOf(e, "The demo accounts are resting. Try again in a moment."));
      setBusy(null);
    }
  }

  const roles: Role[] = only ? [only] : ["customer", "organiser"];
  return (
    <div className={cn("grid gap-2", className)}>
      <div className={cn("grid gap-2", roles.length > 1 && "sm:grid-cols-2")}>
        {roles.map((r) => (
          <Button
            key={r}
            type="button"
            variant={tone === "paper" ? "paper" : "outline"}
            size="sm"
            disabled={busy !== null}
            onClick={() => go(r)}
            className="h-auto flex-col items-start gap-0 py-2 text-left normal-case"
          >
            <span className="font-cond text-lg font-bold uppercase">{busy === r ? "Signing in…" : COPY[r].label}</span>
            <span className={cn("font-sans text-xs font-medium tracking-normal", tone === "paper" ? "text-ink-2" : "text-muted-foreground")}>
              {COPY[r].sub}
            </span>
          </Button>
        ))}
      </div>
      {error && (
        <p role="alert" className={cn("text-sm font-medium", tone === "paper" ? "text-red-dark" : "text-amber")}>
          {error}
        </p>
      )}
    </div>
  );
}
