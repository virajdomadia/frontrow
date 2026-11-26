import type { Metadata } from "next";
import { BusinessDecision } from "@/components/staff/BusinessDecision";
import { staffMe } from "@/components/staff/session";
import { Card, Empty, PageHead, StatusPill, Tabs, shortDate } from "@/components/staff/ui";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "Approvals" };

const STATUSES = ["pending", "verified", "rejected"] as const;
type Status = (typeof STATUSES)[number];
const LABEL: Record<Status, string> = { pending: "Waiting", verified: "Verified", rejected: "Rejected" };

type Props = { searchParams: Promise<{ status?: string | string[] }> };

/** T4 · approvals: new cinema businesses, approve (their shows go public) or reject with a reason. */
export default async function BusinessesPage({ searchParams }: Props) {
  const raw = (await searchParams).status;
  const status: Status = STATUSES.includes(raw as Status) ? (raw as Status) : "pending";
  const [me, businesses] = await Promise.all([staffMe(), api("/staff/businesses", { auth: true, searchParams: { status } })]);
  const demo = !!me?.is_demo;

  return (
    <>
      <PageHead
        title="Cinema approvals"
        sub="Every new business is checked once — call the phone number, look at the cinemas — before anything it builds goes public."
      />
      <Tabs
        current={status}
        items={STATUSES.map((s) => ({ key: s, href: `/staff/businesses?status=${s}`, label: LABEL[s] }))}
      />
      {businesses.length === 0 ? (
        <Empty
          title={status === "pending" ? "Nothing waiting" : `No ${LABEL[status].toLowerCase()} businesses`}
          body={status === "pending" ? "New registrations from the business door appear here." : "Decisions you make show up here."}
        />
      ) : (
        <ul className="grid list-none gap-4 p-0 xl:grid-cols-2">
          {businesses.map((b) => (
            <li key={b.id}>
              <Card className="grid h-full content-start gap-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid gap-1">
                    <h2 className="font-cond text-3xl leading-none font-extrabold uppercase">{b.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      Registered {shortDate(b.created_at)} · {b.phone}
                      {b.verified_at && ` · verified ${shortDate(b.verified_at)}`}
                    </p>
                  </div>
                  <StatusPill status={b.status} />
                </div>

                {b.review_note && (
                  <p className="rounded-btn bg-red/8 px-3 py-2 text-sm text-ink">
                    <b className="text-red-dark">Rejected:</b> {b.review_note}
                  </p>
                )}

                <dl className="grid gap-3 text-sm sm:grid-cols-[110px_1fr]">
                  <dt className="font-semibold text-ink-2">Owners</dt>
                  <dd className="m-0">
                    {b.owners.length ? (
                      b.owners.map((o) => (
                        <div key={o.email}>
                          {o.name} · <a href={`mailto:${o.email}`}>{o.email}</a>
                        </div>
                      ))
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </dd>
                  <dt className="font-semibold text-ink-2">Cinemas</dt>
                  <dd className="m-0 grid gap-2">
                    {b.cinemas.length ? (
                      b.cinemas.map((c) => (
                        <div key={c.id}>
                          <b>{c.name}</b> · {c.area}
                          <div className="text-muted-foreground">{c.address}</div>
                          <div className="text-xs text-ink-3">
                            {c.screens} {c.screens === 1 ? "screen" : "screens"} · {c.seats} seats
                          </div>
                        </div>
                      ))
                    ) : (
                      <span className="text-muted-foreground">No cinemas set up yet</span>
                    )}
                  </dd>
                  <dt className="font-semibold text-ink-2">Shows</dt>
                  <dd className="m-0">
                    {b.scheduled_shows} upcoming {b.scheduled_shows === 1 ? "show" : "shows"}
                    {b.status !== "verified" && b.scheduled_shows > 0 && (
                      <span className="text-muted-foreground"> — public as soon as you approve</span>
                    )}
                  </dd>
                </dl>

                <div className="mt-auto border-t border-dashed border-ink/20 pt-4">
                  <BusinessDecision id={b.id} name={b.name} status={b.status} demo={demo} />
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
