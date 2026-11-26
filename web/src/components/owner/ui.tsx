import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Console building blocks: paper pages, card-white panels, cream stub cards (colour change 2026-11-15). */

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

export function PaperCard({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("fr-stub p-5 text-ink shadow-[0_14px_34px_rgb(42_11_30_/_.10)] sm:p-6", className)}>
      {children}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-card border border-border bg-plum-2 px-4 py-3.5">
      <div className="text-xs font-semibold tracking-[.1em] text-muted-foreground uppercase">{label}</div>
      <div className="mt-1 font-cond text-[34px] leading-none font-extrabold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-faint">{hint}</div>}
    </div>
  );
}

const badgeBase = "inline-block rounded-sm px-[7px] py-[3px] text-[11px] font-semibold tracking-[.06em] uppercase";

export type BadgeKind = "public" | "private" | "pending" | "verified" | "rejected" | "suspended" | "cancelled" | "past" | "open" | "added" | "declined";

export function StatusBadge({ status }: { status: BadgeKind }) {
  const look = {
    public: "bg-mint/15 text-[#1f6e57]",
    verified: "bg-mint/15 text-[#1f6e57]",
    added: "bg-mint/15 text-[#1f6e57]",
    private: "bg-amber/15 text-[#8a4a10]",
    pending: "bg-amber/15 text-[#8a4a10]",
    open: "bg-amber/15 text-[#8a4a10]",
    rejected: "bg-red/12 text-red-dark",
    declined: "bg-red/12 text-red-dark",
    suspended: "bg-red/12 text-red-dark",
    cancelled: "bg-red/12 text-red-dark",
    past: "bg-ink/8 text-ink-3",
  }[status];
  const text = {
    public: "Public", private: "Not public yet", pending: "Pending verification", verified: "Verified",
    rejected: "Rejected", suspended: "Suspended", cancelled: "Cancelled", past: "Played",
    open: "Open", added: "Added", declined: "Declined",
  }[status];
  return <span className={cn(badgeBase, look)}>{text}</span>;
}

/** Sold share as a bar; amber from 70 % (the public "filling fast" line). */
export function FillBar({ sold, total, className }: { sold: number; total: number; className?: string }) {
  const pct = total ? Math.min(100, Math.round((sold / total) * 100)) : 0;
  return (
    <div className={cn("grid gap-1", className)}>
      <div
        role="meter"
        aria-label="Seats sold"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={sold}
        aria-valuetext={`${sold} of ${total} sold, ${pct}%`}
        className="h-1.5 overflow-hidden rounded-full bg-ink/10"
      >
        <div className={cn("h-full rounded-full", pct >= 70 ? "bg-amber" : "bg-classic")} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {sold} / {total} sold · {pct}%
      </div>
    </div>
  );
}

export function Empty({
  title,
  body,
  href,
  cta,
}: {
  title: string;
  body: string;
  href?: string;
  cta?: string;
}) {
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

/** Paper-form field styles, shared by the cinema / screen / schedule forms. */
export const field = {
  label: "grid gap-1.5 text-sm font-semibold text-ink-2",
  input:
    "w-full rounded-btn border border-ink/25 bg-white/70 px-3 py-2.5 text-[16px] font-normal text-ink placeholder:text-ink-3 focus-visible:border-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber aria-invalid:border-red-dark",
  hint: "text-xs font-normal text-ink-3",
  error: "text-xs font-medium text-red-dark",
  legend: "mb-2 text-sm font-semibold text-ink-2",
};

export function FormError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
      {message}
    </p>
  );
}
