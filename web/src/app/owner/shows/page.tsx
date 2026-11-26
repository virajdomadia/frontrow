import Link from "next/link";
import { dayName } from "@/components/owner/format";
import { ShowsTable } from "@/components/owner/ShowsTable";
import { Empty, PageHead } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export const metadata = { title: "Shows" };

type Props = { searchParams: Promise<{ date?: string | string[] }> };

/** O6 · shows by day across every cinema, with a 14-day strip and the bulk scheduler. */
export default async function OwnerShowsPage({ searchParams }: Props) {
  const raw = (await searchParams).date;
  const date = typeof raw === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : undefined;
  const data = await api("/owner/shows", { auth: true, searchParams: { date } });
  const total = data.shows.reduce((a, s) => a + s.sold, 0);
  return (
    <>
      <PageHead
        title="Shows"
        sub={`${dayName(data.date)} · ${data.shows.length} shows · ${total.toLocaleString("en-IN")} tickets sold`}
        action={
          <Link href="/owner/shows/new" className={buttonVariants()}>
            Schedule shows
          </Link>
        }
      />
      <nav aria-label="Days" className="-mx-4 mb-6 overflow-x-auto px-4">
        <ul className="flex list-none gap-2 p-0">
          {data.dates.map((d, i) => {
            const on = d.date === data.date;
            return (
              <li key={d.date}>
                <Link
                  href={`/owner/shows?date=${d.date}`}
                  aria-current={on ? "date" : undefined}
                  className={cn(
                    "grid min-w-[76px] justify-items-center rounded-card border px-3 py-2 no-underline",
                    on ? "border-ink bg-ink text-paper" : "border-border bg-plum-2 hover:border-ink/40",
                  )}
                >
                  <span className="text-xs font-semibold tracking-[.08em] uppercase">{i === 0 ? "Today" : dayName(d.date).split(" ")[0]}</span>
                  <span className="font-cond text-2xl font-bold">{dayName(d.date).split(" ")[1]}</span>
                  <span className={cn("text-xs", on ? "text-paper/80" : "text-ink-3")}>{d.show_count} shows</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {data.shows.length ? (
        <ShowsTable shows={data.shows} />
      ) : (
        <Empty
          title="Nothing scheduled this day"
          body="Pick a film, a screen, the days and times and a price per tier — Frontrow creates every show and refuses overlaps."
          href="/owner/shows/new"
          cta="Schedule shows"
        />
      )}
    </>
  );
}
