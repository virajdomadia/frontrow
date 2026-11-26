import Image from "next/image";
import Link from "next/link";
import { duration } from "@/lib/format";
import { FilmRequestForm } from "@/components/owner/FilmRequestForm";
import { stamp } from "@/components/owner/format";
import { PageHead, StatusBadge } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";

export const metadata = { title: "Films" };

/** O5 · pick a film from the shared catalogue to schedule, or ask staff for a missing one. */
export default async function OwnerFilmsPage() {
  const [catalogue, requests] = await Promise.all([
    api("/films", { auth: true }),
    api("/owner/film-requests", { auth: true }),
  ]);
  return (
    <>
      <PageHead title="Films" sub="The shared catalogue Frontrow staff keep. Pick one to schedule shows of it." />
      <div className="grid items-start gap-8 xl:grid-cols-[1fr_380px]">
        <ul className="grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {catalogue.films.map((f) => (
            <li key={f.id} className="grid grid-cols-[84px_1fr] gap-3 rounded-card border border-border bg-plum-2 p-3">
              <div className="relative aspect-[2/3] overflow-hidden rounded-btn bg-paper-2">
                <Image src={f.poster_url} alt="" fill sizes="84px" className="object-cover" />
              </div>
              <div className="grid content-start gap-1.5">
                <h2 className="font-cond text-xl leading-none font-bold uppercase">{f.title}</h2>
                <p className="text-xs text-ink-2">
                  {f.cert} · {duration(f.runtime_min)} · {f.genres.join(", ")}
                </p>
                <p className="text-xs text-ink-3">
                  {f.languages.join(", ")} · {f.formats.join(" / ")}
                </p>
                {f.status === "coming_soon" && <span className="text-xs font-semibold text-[#8a4a10]">Coming soon · releases {f.release_date}</span>}
                <Link href={`/owner/shows/new?film=${f.id}`} className={buttonVariants({ size: "sm", className: "mt-1 justify-self-start" })}>
                  Schedule shows
                </Link>
              </div>
            </li>
          ))}
        </ul>
        <aside className="grid gap-6">
          <FilmRequestForm />
          <section aria-labelledby="requests">
            <h2 id="requests" className="mb-2 font-cond text-2xl font-bold uppercase">
              Your requests
            </h2>
            {requests.length ? (
              <ul className="grid list-none gap-2 p-0">
                {requests.map((r) => (
                  <li key={r.id} className="rounded-card border border-border bg-plum-2 px-4 py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <b className="font-semibold">{r.title}</b>
                      <StatusBadge status={r.status} />
                    </div>
                    <p className="mt-0.5 text-xs text-ink-3">Asked {stamp(r.created_at)}</p>
                    {r.note && <p className="mt-1 text-ink-2">{r.note}</p>}
                    {r.reply && <p className="mt-1 text-ink-2">Staff: “{r.reply}”</p>}
                    {r.film && (
                      <Link href={`/owner/shows/new?film=${r.film.id}`} className="mt-1 inline-block font-semibold underline underline-offset-4">
                        {r.film.title} is in — schedule it →
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">No requests yet.</p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}
