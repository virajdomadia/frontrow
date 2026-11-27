"use client";

import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { AUTH_EVENT, announceAuth, samePage } from "@/lib/auth-events";
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
  const path = usePathname();
  const [busy, setBusy] = useState<DemoRole | null>(null);
  const [error, setError] = useState("");
  const [current, setCurrent] = useState<DemoRole | null>(null);

  // Already signed in as a demo role (the header announces who): that button continues instead.
  useEffect(() => {
    const onAuth = (e: Event) => {
      const me = (e as CustomEvent<Me | null>).detail;
      setCurrent(!me?.is_demo ? null : me.is_staff ? "staff" : me.businesses.length ? "owner" : "customer");
    };
    window.addEventListener(AUTH_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_EVENT, onAuth);
  }, []);

  async function go(as: DemoRole) {
    if (as === current && !onDone) return router.push(safeNext(next, COPY[as].home));
    setBusy(as);
    setError("");
    try {
      const me = await send<Me>("POST", "/auth/demo", { as });
      announceAuth(me);
      if (onDone) return onDone(me);
      const target = safeNext(next, COPY[as].home);
      // Already there (the demo customer on the home page): nothing navigates, so this button
      // would stay on "Signing in…" — finish here instead.
      if (samePage(path, target)) setBusy(null);
      router.push(target);
      router.refresh();
    } catch (e) {
      setError(messageOf(e, "The demo accounts are resting. Try again in a moment."));
      setBusy(null);
    }
  }

  const list: DemoRole[] = only ? [only] : roles;
  return (
    <div className={cn("grid gap-2", className)}>
      <div className={cn("grid gap-2", list.length === 3 && "grid-cols-3", list.length === 2 && "grid-cols-2")}>
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
            <span className="inline-flex items-center gap-1.5 font-cond text-lg font-bold uppercase">
              {busy === r && <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" />}
              {busy === r ? "Signing in…" : r === current ? `${COPY[r].label} · continue` : COPY[r].label}
            </span>
            <span className={cn("hidden font-sans text-xs font-medium tracking-normal sm:block", tone === "dark" ? "text-oxblood-ink/80" : "text-ink-2")}>
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
