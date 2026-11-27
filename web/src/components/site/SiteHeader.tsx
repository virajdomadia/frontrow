import Link from "next/link";
import { cn } from "@/lib/utils";
import { AccountLinks } from "./AccountLinks";
import { Logo } from "./Logo";

export type NavItem = { href: string; label: string; key: string };

const CUSTOMER_NAV: NavItem[] = [
  { key: "movies", href: "/movies", label: "Movies" },
  { key: "tickets", href: "/my-tickets", label: "My tickets" },
  { key: "business", href: "/business", label: "For cinemas" },
];

/**
 * The oxblood header with the torn-stub edge (04-ui-mockups, colour change 2026-11-15). One
 * header for every role: customers get Movies / My tickets / For cinemas; the owner and staff
 * consoles pass their own `nav` and a `badge` naming the console.
 */
export function SiteHeader({
  active,
  nav = CUSTOMER_NAV,
  badge,
  wide = false,
}: {
  active?: string;
  nav?: NavItem[];
  badge?: string;
  wide?: boolean;
}) {
  return (
    <header className="fr-header no-print">
      <nav
        aria-label="Main"
        className={cn("mx-auto flex items-center justify-between gap-4 py-3.5", wide ? "w-[min(1440px,100%-32px)]" : "w-[min(1240px,100%-32px)]")}
      >
        <div className="flex min-w-0 items-center gap-3">
          <Logo />
          {badge && (
            <span className="hidden rounded-chip border border-oxblood-ink/40 px-2 py-0.5 font-cond text-sm font-semibold tracking-[.08em] uppercase sm:inline">
              {badge}
            </span>
          )}
        </div>
        <ul className="hidden list-none items-center gap-6 p-0 text-[15px] font-medium md:flex">
          {nav.map((l) => (
            <li key={l.key}>
              <Link
                href={l.href}
                aria-current={active === l.key ? "page" : undefined}
                className="text-oxblood-ink/85 no-underline hover:text-white aria-[current=page]:font-semibold aria-[current=page]:text-white aria-[current=page]:underline aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-8"
              >
                {l.label}
              </Link>
            </li>
          ))}
          <li aria-hidden="true" className="h-5 w-px bg-oxblood-ink/30" />
          <li>
            <AccountLinks />
          </li>
        </ul>
        <div className="flex items-center gap-4 text-[15px] font-medium md:hidden">
          <AccountLinks compact />
        </div>
      </nav>
      {nav.length > 0 && (
        <nav aria-label="Sections" className="mx-auto flex w-[min(1240px,100%-32px)] gap-5 overflow-x-auto pb-2.5 text-sm font-medium md:hidden">
          {nav.map((l) => (
            <Link
              key={l.key}
              href={l.href}
              aria-current={active === l.key ? "page" : undefined}
              className="shrink-0 text-oxblood-ink/80 no-underline aria-[current=page]:font-semibold aria-[current=page]:text-white"
            >
              {l.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto mt-20 flex w-[min(1240px,100%-32px)] flex-wrap justify-between gap-2 border-t border-border pt-6 pb-10 text-sm text-muted-foreground">
      <span>Frontrow · a portfolio project by Viraj Domadia</span>
      <span>Bengaluru · real films, fictional cinemas and bookings · posters are our own type</span>
    </footer>
  );
}
