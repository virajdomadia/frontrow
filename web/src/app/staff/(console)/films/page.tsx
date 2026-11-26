import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { staffMe } from "@/components/staff/session";
import { DEMO_REASON, Empty, PageHead, Pill, StatusPill } from "@/components/staff/ui";
import { Button, buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { duration } from "@/lib/format";

export const metadata: Metadata = { title: "Film catalogue" };

/** T2 · the shared film catalogue: staff add every film once; every cinema schedules from it. */
export default async function FilmsPage() {
  const [me, films] = await Promise.all([staffMe(), api("/staff/films", { auth: true })]);
  const demo = !!me?.is_demo;
  const add = demo ? (
    <Button size="sm" disabled title={DEMO_REASON}>
      Add film
    </Button>
  ) : (
    <Link href="/staff/films/new" className={buttonVariants({ size: "sm" })}>
      Add film
    </Link>
  );

  return (
    <>
      <PageHead
        title="Film catalogue"
        sub={`${films.length} films · move a film from coming soon to now showing to ended as its run goes; ended films take no new shows.`}
        action={add}
      />
      {films.length === 0 ? (
        <Empty title="No films yet" body="Add the first film to the shared catalogue." />
      ) : (
        <div className="overflow-x-auto rounded-card border border-border bg-plum-2">
          <table className="w-full min-w-[860px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs tracking-[.08em] text-ink-2 uppercase">
                <th className="px-4 py-3 font-semibold">Film</th>
                <th className="px-3 py-3 font-semibold">Status</th>
                <th className="px-3 py-3 font-semibold">Cert · runtime</th>
                <th className="px-3 py-3 font-semibold">Languages</th>
                <th className="px-3 py-3 font-semibold">Formats</th>
                <th className="px-3 py-3 text-right font-semibold">Upcoming shows</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {films.map((f) => (
                <tr key={f.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="relative h-[60px] w-[42px] shrink-0 overflow-hidden rounded-sm bg-plum-3">
                        <Image src={f.poster_url} alt="" fill sizes="256px" className="object-cover" />
                      </div>
                      <div>
                        <div className="font-cond text-xl leading-tight font-bold uppercase">{f.title}</div>
                        <div className="text-xs text-muted-foreground">{f.genres.join(" · ")}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <StatusPill status={f.status} />
                  </td>
                  <td className="px-3 py-3">
                    <Pill tone="grey">{f.cert}</Pill> <span className="ml-1">{duration(f.runtime_min)}</span>
                  </td>
                  <td className="px-3 py-3">{f.languages.join(", ")}</td>
                  <td className="px-3 py-3">{f.formats.join(" · ")}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{f.scheduled_shows}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/staff/films/${f.id}`} className="font-semibold">
                      {demo ? "View" : "Edit"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
