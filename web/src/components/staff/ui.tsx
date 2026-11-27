import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Staff console building blocks: paper pages, cream cards, Barlow Condensed heads. */

export const DEMO_REASON = "Demo staff can look around but not make changes.";

export function PageHead({
  title,
  sub,
  action,
  back,
}: {
  title: string;
  sub?: React.ReactNode;
  action?: React.ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="grid gap-1.5">
        {back && (
          <Link href={back.href} className="text-sm text-muted-foreground no-underline hover:text-screen">
            ← {back.label}
          </Link>
        )}
        <h1 className="font-cond text-[clamp(34px,5vw,52px)] leading-[.95] font-extrabold uppercase">{title}</h1>
        {sub && <p className="text-sm text-muted-foreground">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("rounded-card border border-border bg-plum-2 p-5", className)}>{children}</div>;
}

type Tone = "green" | "amber" | "red" | "grey" | "blue";
const TONES: Record<Tone, string> = {
  green: "bg-mint/15 text-[#1f6e58]",
  amber: "bg-amber/15 text-[#8a4a10]",
  red: "bg-red/12 text-red-dark",
  grey: "bg-ink/8 text-ink-2",
  blue: "bg-classic/15 text-[#2a5f91]",
};

export function Pill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-block rounded-sm px-[7px] py-[3px] text-xs font-semibold tracking-[.06em] uppercase", TONES[tone])}>
      {children}
    </span>
  );
}

const STATUS: Record<string, [Tone, string]> = {
  pending: ["amber", "Pending"],
  verified: ["green", "Verified"],
  rejected: ["red", "Rejected"],
  suspended: ["grey", "Suspended"],
  open: ["amber", "Open"],
  added: ["green", "Added"],
  declined: ["red", "Declined"],
  coming_soon: ["blue", "Coming soon"],
  now_showing: ["green", "Now showing"],
  ended: ["grey", "Ended"],
};

export function StatusPill({ status }: { status: string }) {
  const [tone, text] = STATUS[status] ?? ["grey", status];
  return <Pill tone={tone}>{text}</Pill>;
}

/** Link tabs (`?status=`), the current one marked for screen readers. */
export function Tabs({ items, current }: { items: { href: string; label: string; key: string }[]; current: string }) {
  return (
    <nav aria-label="Filter" className="mb-6 flex flex-wrap gap-2">
      {items.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          aria-current={t.key === current ? "page" : undefined}
          className="rounded-chip border border-ink/20 px-3 py-1.5 font-cond text-base font-semibold tracking-[.05em] text-ink-2 uppercase no-underline hover:border-ink aria-[current=page]:border-ink aria-[current=page]:bg-ink aria-[current=page]:text-paper"
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

export function Empty({ title, body, href, cta }: { title: string; body: string; href?: string; cta?: string }) {
  return (
    <div className="grid justify-items-start gap-3 rounded-card border border-dashed border-ink/25 px-6 py-8">
      <h2 className="font-cond text-2xl font-bold uppercase">{title}</h2>
      <p className="max-w-[52ch] text-muted-foreground">{body}</p>
      {href && cta && (
        <Link href={href} className={buttonVariants({ size: "sm" })}>
          {cta}
        </Link>
      )}
    </div>
  );
}

export function DemoNotice() {
  return (
    <p role="note" className="mb-6 rounded-card border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-ink">
      <b>You&apos;re the demo staff account.</b> {DEMO_REASON} Approve, reject, add and edit buttons are switched off.
    </p>
  );
}

export function FormError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
      {message}
    </p>
  );
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" });

/** "26 Nov 2026" in IST. */
export function shortDate(iso: string) {
  return dateFmt.format(new Date(iso));
}
