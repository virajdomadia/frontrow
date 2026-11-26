import Link from "next/link";
import { notFound } from "next/navigation";
import { CinemaForm } from "@/components/owner/CinemaForm";
import { TEMPLATE_LABEL } from "@/components/owner/format";
import { Empty, PageHead } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Cinema" };

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ new?: string; added?: string }> };

/** O3/O4 · one cinema: its details (editable) and its screens. */
export default async function CinemaPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { new: isNew, added } = await searchParams;
  let cinema;
  try {
    cinema = await api("/owner/cinemas/{cinema_id}", { params: { cinema_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  return (
    <>
      <PageHead title={cinema.name} sub={cinema.address} back={{ href: "/owner/cinemas", label: "Cinemas" }} />
      {(isNew || added) && (
        <p role="status" className="mb-6 rounded-card border border-mint/40 bg-mint/10 px-4 py-3 text-[15px] text-ink">
          {added ? `${added} is ready — seats generated.` : "Cinema added."} Next: {added ? "schedule shows on it" : "add its screens"}.
        </p>
      )}
      <div className="grid items-start gap-8 lg:grid-cols-[1fr_1fr]">
        <section aria-labelledby="screens" className="grid gap-3">
          <div className="flex items-end justify-between gap-3">
            <h2 id="screens" className="font-cond text-3xl font-bold uppercase">
              Screens
            </h2>
            <Link href={`/owner/cinemas/${cinema.id}/screens/new`} className={buttonVariants({ size: "sm" })}>
              Add screen
            </Link>
          </div>
          {cinema.screens.length ? (
            <ul className="grid list-none gap-2 p-0">
              {cinema.screens.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-plum-2 px-4 py-3">
                  <div>
                    <Link href={`/owner/screens/${s.id}`} className="font-cond text-xl font-bold uppercase">
                      {s.name}
                    </Link>
                    <p className="text-sm text-ink-2">
                      {TEMPLATE_LABEL[s.template]} · {s.seat_count} seats · {s.formats.join(" / ")} · {s.tiers.map((t) => t.label).join(", ")}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <span className="self-center text-sm text-ink-3">{s.upcoming_shows} upcoming</span>
                    <Link href={`/owner/shows/new?screen=${s.id}`} className={buttonVariants({ variant: "paper", size: "sm" })}>
                      Schedule
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="No screens yet"
              body="A screen is a seat map: pick a template and size, and Frontrow generates every seat."
              href={`/owner/cinemas/${cinema.id}/screens/new`}
              cta="Add screen"
            />
          )}
        </section>
        <section aria-labelledby="details" className="grid gap-3">
          <h2 id="details" className="font-cond text-3xl font-bold uppercase">
            Details
          </h2>
          <CinemaForm cinema={cinema} />
        </section>
      </div>
    </>
  );
}
