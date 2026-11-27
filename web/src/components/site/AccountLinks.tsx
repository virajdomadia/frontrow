"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AUTH_EVENT, announceAuth } from "@/lib/auth-events";
import { send } from "@/lib/client";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Who's signed in, read in the browser so the catalogue pages around it stay statically cached.
 * Signed out: "Sign in". Signed in: the account's doors — Cinema console (business access),
 * Staff (staff flag) — and "Sign out". One email = one person, so a customer link is always there.
 */
export function AccountLinks({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let live = true;
    send<Me>("GET", "/auth/me")
      // Announced, not just stored: the home page's demo buttons relabel for who's signed in.
      .then((m) => live && announceAuth(m))
      .catch(() => live && announceAuth(null));
    return () => {
      live = false;
    };
  }, [path]);

  // A sign-in elsewhere on the page (demo buttons, the booking sign-in dialog) updates the header
  // right away, even when the URL doesn't change.
  useEffect(() => {
    const onAuth = (e: Event) => setMe((e as CustomEvent<Me | null>).detail);
    window.addEventListener(AUTH_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_EVENT, onAuth);
  }, []);

  async function signOut() {
    await send("POST", "/auth/sign-out").catch(() => undefined);
    announceAuth(null);
    router.push("/");
    router.refresh();
  }

  const link = "text-oxblood-ink/85 no-underline hover:text-white";
  if (me === undefined) return <span className="inline-block min-w-[64px]" aria-hidden="true" />;
  if (me === null)
    return (
      <Link
        href={`/sign-in?next=${encodeURIComponent(path)}`}
        className="rounded-btn bg-oxblood-ink px-3 py-1.5 font-cond text-base font-bold tracking-[.05em] text-oxblood uppercase no-underline hover:bg-white"
      >
        Sign in
      </Link>
    );
  const first = me.name.split(/[\s(]/)[0] || "You";
  return (
    <span className="inline-flex items-center gap-4">
      {me.businesses.length > 0 && (
        <Link href="/owner" className={link}>
          {compact ? "Console" : "Cinema console"}
        </Link>
      )}
      {me.is_staff && (
        <Link href="/staff/businesses?status=pending" className={link}>
          Staff
        </Link>
      )}
      <span className="flex items-center gap-2">
        <span aria-hidden="true" className="grid size-7 place-items-center rounded-full bg-oxblood-ink font-cond text-sm font-bold text-oxblood uppercase">
          {first[0]}
        </span>
        <span className={cn("max-w-[10ch] truncate", compact && "sr-only")}>{first}</span>
      </span>
      <button type="button" onClick={signOut} className={cn(link, "cursor-pointer border-0 bg-transparent p-0 font-[inherit] text-[inherit]")}>
        Sign out
      </button>
    </span>
  );
}
