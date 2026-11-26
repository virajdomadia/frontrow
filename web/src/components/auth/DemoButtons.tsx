"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { messageOf, safeNext, send } from "@/lib/client";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";

export type DemoRole = "customer" | "owner" | "staff";

const COPY: Record<DemoRole, { label: string; sub: string; home: string }> = {
  customer: { label: "Demo customer", sub: "Book seats · see your tickets", home: "/" },
  owner: { label: "Demo theatre owner", sub: "Orbit Cinemas · shows, bookings, door", home: "/owner" },
  staff: { label: "Demo Frontrow staff", sub: "Catalogue · approvals (view only)", home: "/staff/businesses?status=pending" },
};

/**
 * One click, no email (R1): the seeded demo customer, theatre owner (Orbit Cinemas) or staff
 * member. On the home page, the three sign-in doors, and inline at Proceed (customer only).
 */
export function DemoButtons({
  next,
  onDone,
  only,
  roles = ["customer", "owner", "staff"],
  tone = "paper",
  className,
}: {
  next?: string;
  onDone?: (me: Me) => void;
  only?: DemoRole;
  roles?: DemoRole[];
  tone?: "paper" | "dark";
  className?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<DemoRole | null>(null);
  const [error, setError] = useState("");

  async function go(as: DemoRole) {
    setBusy(as);
    setError("");
    try {
      const me = await send<Me>("POST", "/auth/demo", { as });
      if (onDone) return onDone(me);
      router.push(safeNext(next, COPY[as].home));
      router.refresh();
    } catch (e) {
      setError(messageOf(e, "The demo accounts are resting. Try again in a moment."));
      setBusy(null);
    }
  }

  const list: DemoRole[] = only ? [only] : roles;
  return (
    <div className={cn("grid gap-2", className)}>
      <div className={cn("grid gap-2", list.length === 3 && "sm:grid-cols-3", list.length === 2 && "sm:grid-cols-2")}>
        {list.map((r) => (
          <Button
            key={r}
            type="button"
            variant={tone === "dark" ? "outline" : "paper"}
            size="sm"
            disabled={busy !== null}
            onClick={() => go(r)}
            className="h-auto flex-col items-start gap-0 py-2 text-left whitespace-normal normal-case"
          >
            <span className="font-cond text-lg font-bold uppercase">{busy === r ? "Signing in…" : COPY[r].label}</span>
            <span className={cn("font-sans text-xs font-medium tracking-normal", tone === "dark" ? "text-oxblood-ink/80" : "text-ink-2")}>
              {COPY[r].sub}
            </span>
          </Button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm font-medium text-red-dark">
          {error}
        </p>
      )}
    </div>
  );
}
