import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { rupees, when } from "@/lib/format";
import { requireMe } from "@/lib/session";
import type { TicketGroup } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "My tickets", robots: { index: false } };

/** C11 · My tickets: the signed-in customer's bookings, upcoming first, then what they've already seen. */
export default async function MyTicketsPage() {
  const me = await requireMe("/my-tickets");
  const { upcoming, past } = await api("/my/tickets", { auth: true });

  return (
    <>
      <SiteHeader active="tickets" />
      <main id="main" className="mx-auto grid w-[min(1240px,100%-32px)] gap-10 pt-10">
        <div className="grid gap-2">
          <p className="text-sm text-muted-foreground">Signed in as {me.email}</p>
          <h1 className="font-cond text-[clamp(44px,6vw,72px)] leading-[.92] font-extrabold uppercase">My tickets</h1>
        </div>

        <section aria-labelledby="upcoming" className="grid gap-4">
          <h2 id="upcoming" className="font-cond text-3xl font-bold uppercase">
            Upcoming <span className="text-faint">· {upcoming.length}</span>
          </h2>
          {upcoming.length ? (
            <ul className="grid list-none gap-3 p-0 md:grid-cols-2">
              {upcoming.map((g) => (
                <li key={g.order_id}>
                  <Group g={g} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="grid justify-items-start gap-3 rounded-card bg-plum-2 px-5 py-6">
              <p className="text-muted-foreground">No upcoming shows yet. Pick a seat — it&apos;s held for you for ten minutes.</p>
              <Link href="/movies" className={buttonVariants({ size: "sm" })}>
                Find a movie
              </Link>
            </div>
          )}
        </section>

        {past.length > 0 && (
          <section aria-labelledby="past" className="grid gap-4">
            <h2 id="past" className="font-cond text-3xl font-bold text-muted-foreground uppercase">
              Past <span className="text-faint">· {past.length}</span>
            </h2>
            <ul className="grid list-none gap-3 p-0 md:grid-cols-2">
              {past.map((g) => (
                <li key={g.order_id}>
                  <Group g={g} past />
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <SiteFooter />
    </>
  );
}

function Group({ g, past = false }: { g: TicketGroup; past?: boolean }) {
  const st = g.show;
  return (
    <Link
      href={`/tickets/${g.order_id}`}
      className={cn(
        "group grid grid-cols-[72px_1fr] gap-4 rounded-card p-4 no-underline transition-colors sm:grid-cols-[88px_1fr]",
        past ? "bg-plum-2/60 hover:bg-plum-2" : "border border-border bg-paper text-ink hover:bg-paper-2",
      )}
    >
      <Image
        src={st.film.poster_url}
        alt=""
        width={88}
        height={120}
        sizes="88px"
        className={cn("h-[100px] w-[72px] rounded-[6px] object-cover sm:h-[120px] sm:w-[88px]", past && "opacity-60 grayscale")}
      />
      <div className="grid content-start gap-1">
        <b className="font-cond text-[26px] leading-none font-extrabold uppercase">{st.film.title}</b>
        <span className={cn("text-sm", past ? "text-muted-foreground" : "text-ink-2")}>
          {when(st.starts_at)} · {st.cinema.name} · {st.language} {st.format}
        </span>
        <span className={cn("mt-1 font-cond text-lg font-bold tracking-[.03em]", past ? "text-faint" : "text-red-dark")}>
          {g.seats.join(" · ")}
        </span>
        <span className={cn("text-xs", past ? "text-faint" : "text-ink-3")}>
          {g.seats.length} {g.seats.length === 1 ? "ticket" : "tickets"} · {g.tier_labels.join(", ")} · {rupees(g.total_paise)}
          {past && g.checked_in > 0 && " · scanned in"}
          <span className="ml-2 font-semibold underline-offset-4 group-hover:underline">{past ? "View" : "Show QR"} →</span>
        </span>
      </div>
    </Link>
  );
}
