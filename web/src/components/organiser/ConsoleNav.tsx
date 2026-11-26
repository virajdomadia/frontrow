"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/organiser", label: "Overview", exact: true },
  { href: "/organiser/venues", label: "Venues" },
  { href: "/organiser/events", label: "Events" },
  { href: "/organiser/showtimes", label: "Showtimes" },
];

/** The console's section tabs; bookings pages live under Showtimes. */
export function ConsoleNav() {
  const path = usePathname();
  const active = (l: (typeof LINKS)[number]) =>
    l.exact ? path === l.href : path.startsWith(l.href) || (l.href.endsWith("showtimes") && path.startsWith("/organiser/bookings"));
  return (
    <nav aria-label="Console" className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none]">
      <ul className="flex list-none gap-1 p-0">
        {LINKS.map((l) => (
          <li key={l.href}>
            <Link
              href={l.href}
              aria-current={active(l) ? "page" : undefined}
              className={cn(
                "block border-b-2 px-3 py-2.5 font-cond text-lg font-bold tracking-[.04em] whitespace-nowrap uppercase no-underline transition-colors",
                active(l) ? "border-red text-screen" : "border-transparent text-muted-foreground hover:text-screen",
              )}
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
