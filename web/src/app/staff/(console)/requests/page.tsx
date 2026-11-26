import type { Metadata } from "next";
import Link from "next/link";
import { RequestActions } from "@/components/staff/RequestActions";
import { staffMe } from "@/components/staff/session";
import { Card, Empty, PageHead, StatusPill, Tabs, shortDate } from "@/components/staff/ui";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "Film requests" };

const STATUSES = ["open", "added", "declined"] as const;
type Status = (typeof STATUSES)[number];
const LABEL: Record<Status, string> = { open: "Open", added: "Added", declined: "Declined" };

type Props = { searchParams: Promise<{ status?: string | string[] }> };

/** T3 · films owners asked for: add to the catalogue, link one that's there, or decline. */
export default async function RequestsPage({ searchParams }: Props) {
  const raw = (await searchParams).status;
  const status: Status = STATUSES.includes(raw as Status) ? (raw as Status) : "open";
  const [me, requests, films] = await Promise.all([
    staffMe(),
    api("/staff/film-requests", { auth: true, searchParams: { status } }),
    status === "open" ? api("/staff/films", { auth: true }) : Promise.resolve([]),
  ]);
  const demo = !!me?.is_demo;
  const options = films.filter((f) => f.status !== "ended").map((f) => ({ id: f.id, title: f.title }));

  return (
    <>
      <PageHead
        title="Film requests"
        sub="Theatre owners ask for films that aren't in the shared catalogue yet. Add each film once; every cinema can then schedule it."
      />
      <Tabs current={status} items={STATUSES.map((s) => ({ key: s, href: `/staff/requests?status=${s}`, label: LABEL[s] }))} />
      {requests.length === 0 ? (
        <Empty
          title={status === "open" ? "No open requests" : `No ${LABEL[status].toLowerCase()} requests`}
          body={status === "open" ? "When an owner asks for a missing film, it lands here." : "Answered requests show up here."}
        />
      ) : (
        <ul className="grid list-none gap-4 p-0 lg:grid-cols-2">
          {requests.map((r) => (
            <li key={r.id}>
              <Card className="grid h-full content-start gap-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid gap-1">
                    <h2 className="font-cond text-3xl leading-none font-extrabold uppercase">{r.title}</h2>
                    <p className="text-sm text-muted-foreground">
                      {r.business.name} · asked {shortDate(r.created_at)}
                    </p>
                  </div>
                  <StatusPill status={r.status} />
                </div>
                {r.note && <p className="text-[15px] text-ink-2">“{r.note}”</p>}
                {r.status === "added" && r.film && (
                  <p className="text-sm">
                    Added as{" "}
                    <Link href={`/movies/${r.film.slug}`} className="font-semibold">
                      {r.film.title}
                    </Link>
                  </p>
                )}
                {r.status === "declined" && r.reply && (
                  <p className="rounded-btn bg-red/8 px-3 py-2 text-sm">
                    <b className="text-red-dark">Declined:</b> {r.reply}
                  </p>
                )}
                {r.status === "open" && (
                  <div className="mt-auto border-t border-dashed border-ink/20 pt-4">
                    <RequestActions id={r.id} title={r.title} films={options} demo={demo} />
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
