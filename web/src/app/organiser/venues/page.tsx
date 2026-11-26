import Image from "next/image";
import Link from "next/link";
import { TEMPLATE_LABEL } from "@/components/organiser/format";
import { Empty, PageHead } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";

export const metadata = { title: "Venues" };

/** S10 · the organiser's venues, each generated once from a template. */
export default async function VenuesPage() {
  const venues = await api("/organiser/venues", { auth: true });
  const seats = venues.reduce((a, v) => a + v.seat_count, 0);
  return (
    <>
      <PageHead
        title="Venues"
        sub={venues.length ? `${venues.length} ${venues.length === 1 ? "venue" : "venues"} · ${seats.toLocaleString("en-IN")} seats` : undefined}
        action={
          <Link href="/organiser/venues/new" className={buttonVariants({ size: "sm" })}>
            New venue
          </Link>
        }
      />
      {venues.length ? (
        <ul className="grid list-none gap-3 p-0 md:grid-cols-2">
          {venues.map((v) => (
            <li key={v.id}>
              <Link
                href={`/organiser/venues/${v.id}`}
                className="group grid grid-cols-[96px_1fr] gap-4 rounded-card bg-plum-2 p-3 no-underline transition-colors hover:bg-plum-3 sm:grid-cols-[128px_1fr]"
              >
                <div className="relative aspect-[4/3] overflow-hidden rounded-btn bg-plum-3">
                  {v.photo_url ? (
                    <Image src={v.photo_url} alt="" fill sizes="128px" className="object-cover" />
                  ) : (
                    <span className="grid size-full place-items-center font-cond text-3xl font-extrabold text-faint uppercase">
                      {v.name.slice(0, 1)}
                    </span>
                  )}
                </div>
                <div className="min-w-0 py-1">
                  <b className="block font-cond text-[22px] leading-tight font-bold group-hover:underline">{v.name}</b>
                  <p className="truncate text-sm text-muted-foreground">{v.address}</p>
                  <p className="mt-1.5 text-xs text-faint">
                    {TEMPLATE_LABEL[v.template]} · {v.seat_count.toLocaleString("en-IN")} seats · {v.tiers.map((t) => t.label).join(" / ")}
                  </p>
                  <p className="mt-0.5 text-xs text-faint">
                    {v.upcoming_showtimes ? `${v.upcoming_showtimes} upcoming ${v.upcoming_showtimes === 1 ? "showtime" : "showtimes"}` : "No upcoming showtimes"}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <Empty
          title="No venues yet"
          body="A venue is a hall with a seat map. Pick a template — cinema grid, stalls + balcony or arena — tune its rows and tiers, and the seats are generated for you."
          href="/organiser/venues/new"
          cta="Create your first venue"
        />
      )}
    </>
  );
}
