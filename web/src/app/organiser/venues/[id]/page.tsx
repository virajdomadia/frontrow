import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATE_LABEL } from "@/components/organiser/format";
import { LayoutPreview } from "@/components/organiser/LayoutPreview";
import { Card, PageHead, Stat } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Venue" };

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ created?: string }> };

/** S10 · one venue: its generated map and what's scheduled there. */
export default async function VenuePage({ params, searchParams }: Props) {
  const { id } = await params;
  const created = (await searchParams).created === "1";
  let venue;
  try {
    venue = await api("/organiser/venues/{venue_id}", { params: { venue_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  return (
    <>
      <PageHead
        title={venue.name}
        sub={venue.address}
        back={{ href: "/organiser/venues", label: "Venues" }}
        action={
          <Link href={`/organiser/showtimes/new?venue_id=${venue.id}`} className={buttonVariants({ size: "sm" })}>
            Schedule a showtime here
          </Link>
        }
      />
      {created && (
        <p role="status" className="mb-5 rounded-card border border-classic/40 bg-classic/10 px-4 py-3 text-sm">
          Venue created with {venue.seat_count.toLocaleString("en-IN")} seats. Next:{" "}
          <Link href="/organiser/events/new" className="font-semibold underline underline-offset-4">
            create an event
          </Link>{" "}
          or{" "}
          <Link href={`/organiser/showtimes/new?venue_id=${venue.id}`} className="font-semibold underline underline-offset-4">
            schedule a showtime
          </Link>
          .
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <LayoutPreview layout={venue.layout} />
        <div className="grid content-start gap-3">
          <Stat label="Seats" value={venue.seat_count.toLocaleString("en-IN")} />
          <Stat label="Upcoming showtimes" value={venue.upcoming_showtimes} />
          <Card>
            <div className="text-xs font-semibold tracking-[.1em] text-muted-foreground uppercase">Template</div>
            <p className="mt-1 font-cond text-xl font-bold uppercase">{TEMPLATE_LABEL[venue.template]}</p>
            <p className="mt-2 text-xs text-faint">
              Tiers, front to back: {venue.tiers.map((t) => t.label).join(" · ")}. Prices are set per showtime.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
