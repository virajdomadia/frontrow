import type { Metadata } from "next";
import { Empty, PageHead } from "@/components/staff/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Emails" };

const STATUS: Record<string, { label: string; tone: string }> = {
  sent: { label: "Sent", tone: "bg-[#1f6e57]/10 text-[#1f6e57]" },
  queued: { label: "Queued", tone: "bg-amber/15 text-ink" },
  failed: { label: "Failed", tone: "bg-red/10 text-red-dark" },
  not_sent: { label: "Not sent: email is off", tone: "bg-ink/10 text-ink" },
  logged: { label: "Logged (local)", tone: "bg-ink/10 text-ink" },
  skipped: { label: "Skipped: demo account", tone: "bg-ink/10 text-ink-2" },
};

/**
 * L5 · The email outbox: every customer email about money (a cancelled show, a refund, a resent
 * ticket) with what happened to it. While SMTP is off this is where you read what customers
 * would have got.
 */
export default async function OutboxPage() {
  const mail = await api("/staff/outbox", { auth: true });
  return (
    <>
      <PageHead
        title="Emails"
        sub="Customer emails about refunds, cancelled shows and resent tickets, newest first. Money is settled first; an email that can't go out never undoes it."
      />
      {mail.length === 0 ? (
        <Empty title="No emails yet" body="When a show is cancelled or a booking refunded, the buyer's email shows up here." />
      ) : (
        <ul className="grid list-none gap-3 p-0">
          {mail.map((m) => (
            <li key={m.id} className="rounded-card border border-border bg-plum-2 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <b className="text-ink">{m.subject}</b>
                <span className={cn("rounded-sm px-2 py-0.5 text-xs font-semibold", STATUS[m.status]?.tone)}>{STATUS[m.status]?.label ?? m.status}</span>
              </div>
              <p className="mt-1 text-sm text-ink-2">
                To {m.to} · {new Date(m.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" })}
                {m.error && <span className="text-red-dark"> · {m.error}</span>}
              </p>
              <details className="mt-2">
                <summary className="cursor-pointer text-sm font-semibold text-ink">Read the email</summary>
                <p className="mt-2 text-sm whitespace-pre-line text-ink">{m.body}</p>
              </details>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
