"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { send } from "@/lib/client";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Who's signed in, read in the browser so the catalog pages around it stay statically cached.
 * Signed out: "Sign in". Customer: "My tickets". Organiser: "Console". Both: "Sign out".
 */
export function AccountLinks({ className, linkClass }: { className?: string; linkClass?: string }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let live = true;
    send<Me>("GET", "/auth/me")
      .then((m) => live && setMe(m))
      .catch(() => live && setMe(null));
    return () => {
      live = false;
    };
  }, [path]);

  async function signOut() {
    await send("POST", "/auth/sign-out").catch(() => undefined);
    setMe(null);
    router.push("/");
    router.refresh();
  }

  const link = cn("text-muted-foreground no-underline hover:text-screen", linkClass);
  if (me === undefined) return <span className={cn("inline-block min-w-[64px]", className)} aria-hidden="true" />;
  if (me === null)
    return (
      <span className={className}>
        <Link href={`/sign-in?next=${encodeURIComponent(path)}`} className={link}>
          Sign in
        </Link>
      </span>
    );
  return (
    <span className={cn("inline-flex items-center gap-5", className)}>
      {me.role === "organiser" ? (
        <Link href="/organiser" className={link}>
          Console
        </Link>
      ) : (
        <Link href="/my-tickets" className={link}>
          My tickets
        </Link>
      )}
      <button type="button" onClick={signOut} className={cn(link, "cursor-pointer border-0 bg-transparent p-0 font-[inherit]")}>
        Sign out
      </button>
    </span>
  );
}
