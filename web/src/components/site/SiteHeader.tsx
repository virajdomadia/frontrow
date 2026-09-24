import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";

export type NavKey = "all" | "movie" | "concert";

const LINKS: { key: NavKey; href: string; label: string }[] = [
  { key: "all", href: "/events", label: "Now showing" },
  { key: "movie", href: "/events?type=movie", label: "Movies" },
  { key: "concert", href: "/events?type=concert", label: "Concerts" },
];

/** Product-page header (S2–S4). `overlay` sits on top of a backdrop photo without a rule. */
export function SiteHeader({ active, overlay = false }: { active?: NavKey; overlay?: boolean }) {
  return (
    <header className={cn("relative z-10", !overlay && "border-b border-border")}>
      <nav aria-label="Main" className="mx-auto flex w-[min(1240px,100%-32px)] items-center justify-between gap-6 py-4">
        <Logo />
        <ul className="hidden list-none gap-6 p-0 text-[15px] font-medium sm:flex">
          {LINKS.map((l) => (
            <li key={l.key}>
              <Link
                href={l.href}
                aria-current={active === l.key ? "page" : undefined}
                className="text-muted-foreground no-underline hover:text-screen aria-[current=page]:font-semibold aria-[current=page]:text-screen"
              >
                {l.label}
              </Link>
            </li>
          ))}
          <li>
            <Link href="/#organisers" className="text-muted-foreground no-underline hover:text-screen">
              For organisers
            </Link>
          </li>
        </ul>
        <Link href="/events" className={cn(buttonVariants({ size: "sm" }), "sm:hidden")}>
          Shows
        </Link>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto mt-20 flex w-[min(1240px,100%-32px)] flex-wrap justify-between gap-2 border-t border-border pt-6 pb-10 text-sm text-muted-foreground">
      <span>Frontrow · a portfolio project by Viraj Domadia</span>
      <span>Fictional shows · all photos CC-licensed</span>
    </footer>
  );
}
