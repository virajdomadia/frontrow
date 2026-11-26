import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATE_LABEL } from "@/components/owner/format";
import { LayoutPreview } from "@/components/owner/LayoutPreview";
import { PageHead, Stat } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Screen" };

type Props = { params: Promise<{ id: string }> };

/** O4 · one screen's seat map, read-only (seats are generated once). */
export default async function ScreenPage({ params }: Props) {
  const { id } = await params;
  let screen;
  try {
    screen = await api("/owner/screens/{screen_id}", { params: { screen_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  return (
    <>
      <PageHead
        title={screen.name}
        sub={`${TEMPLATE_LABEL[screen.template]} · ${screen.formats.join(" / ")}`}
        back={{ href: `/owner/cinemas/${screen.cinema_id}`, label: "Cinema" }}
        action={
          <Link href={`/owner/shows/new?screen=${screen.id}`} className={buttonVariants()}>
            Schedule shows here
          </Link>
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Seats" value={screen.seat_count} />
        <Stat label="Tiers" value={screen.tiers.length} hint={screen.tiers.map((t) => t.label).join(" · ")} />
        <Stat label="Formats" value={screen.formats.length} hint={screen.formats.join(" · ")} />
        <Stat label="Upcoming shows" value={screen.upcoming_shows} />
      </div>
      <LayoutPreview layout={screen.layout} />
    </>
  );
}
